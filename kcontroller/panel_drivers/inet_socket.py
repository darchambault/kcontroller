import logging
import socket
import select
from kcontroller import packets
from kcontroller.dataref import Dataref
from kcontroller.panel_drivers import PanelDriver


class InetSocketPanelDriver(PanelDriver):
    def __init__(self, bind_address, *args, **kwargs):
        super(InetSocketPanelDriver, self).__init__(*args, **kwargs)
        self._bind_address = bind_address
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._connections = []

    def _init(self):
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind(self._bind_address)
        self._server_socket.listen(5)
        self._poller.register(self._server_socket, select.POLLIN)
        logging.debug("Socket panel driver listening on port %s" % self._bind_address[1])

    def _finish(self):
        for connection in self._connections:
            connection[0].close()
        self._connections = []
        self._server_socket.close()

    def _handle_ready(self, ready_list):
        for ready in ready_list:
            if ready[0] == self._server_socket.fileno():
                connection = self._server_socket.accept()
                self._connections.append(connection)
                self._poller.register(connection[0], select.POLLIN)
                logging.debug("Socket panel driver received new connection from %s:%s"
                              % (connection[1][0], connection[1][1]))
            else:
                for connection in self._connections:
                    if ready[0] == connection[0].fileno():
                        if ready[1] & select.POLLHUP:
                            self._poller.unregister(connection[0])
                            connection[0].close()
                            logging.debug("Socket panel driver connection %s:%s hung up"
                                          % (connection[1][0], connection[1][1]))
                            self._connections.remove(connection)
                        else:
                            payload = connection[0].recv(4096)
                            logging.debug("Socket panel driver connection %s:%s received %s byte(s)"
                                          % (connection[1][0], connection[1][1], len(payload)))
                            try:
                                self._parse_payload(payload.strip())
                            except Exception as e:
                                logging.warning("Socket panel driver connection %s:%s error: %s"
                                                % (connection[1][0], connection[1][1], e.message))

    def _handle_inbound_packet(self, packet):
        logging.debug("Socket panel driver received packet %s" % packet)
        if isinstance(packet, packets.SimulationStart):
            payload = "simulation start"
        elif isinstance(packet, packets.SimulationStop):
            payload = "simulation stop"
        elif isinstance(packet, packets.DataWrite):
            dataref = packet.get_dataref()
            payload = "%s %s" % (dataref.get_name(), dataref.get_value())
        else:
            raise NotImplementedError("%s does not implement packet type %s" % (self.__class__, packet.__class__))
        for connection in self._connections:
            connection[0].sendall(payload + "\n")

    def _parse_payload(self, payload):
        if payload.startswith("register "):
            name, data_type = payload[9:].split(" ")
            if data_type == "integer" or data_type == "int":
                data_type = Dataref.TYPE_INTEGER
            elif data_type == "float":
                data_type = Dataref.TYPE_FLOAT
            elif data_type == "command":
                data_type = Dataref.TYPE_COMMAND
            Dataref.register(name, data_type)
            dataref = Dataref.factory(name, None)
            packet = packets.DataSubscribeRequest(dataref)
            self.send_packet_to_exchange(packet)
        elif payload.startswith("command "):
            name, action = payload[8:].split(" ")
            if action == "begin":
                dataref = Dataref.factory(name, Dataref.COMMAND_BEGIN)
                packet = packets.CommandBegin(dataref)
            elif action == "end":
                dataref = Dataref.factory(name, Dataref.COMMAND_END)
                packet = packets.CommandEnd(dataref)
            elif action == "once":
                dataref = Dataref.factory(name, Dataref.COMMAND_ONCE)
                packet = packets.CommandOnce(dataref)
            else:
                raise NotImplementedError("unsupported command action: %s" % action)
            self.send_packet_to_exchange(packet)
        elif payload.startswith("write "):
            name, value = payload[6:].split(" ")
            dataref = Dataref.factory(name, value)
            packet = packets.DataWrite(dataref)
            self.send_packet_to_exchange(packet)
