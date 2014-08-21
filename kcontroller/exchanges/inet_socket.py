import logging
import socket
import select
from kcontroller import packets
from kcontroller.dataref import DatarefInteger, DatarefFloat, DatarefCommand
from kcontroller.exchanges import Exchange


class InetSocketExchange(Exchange):
    def __init__(self, bind_address, *args, **kwargs):
        super(InetSocketExchange, self).__init__(*args, **kwargs)
        self._bind_address = bind_address
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._connection = None
        self._connection_address = None

    def _init(self):
        logging.debug("Exchange listening on port %s" % self._bind_address[1])
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind(self._bind_address)
        self._server_socket.listen(5)
        self._poller.register(self._server_socket, select.POLLIN)

    def _finish(self):
        if self._connection:
            logging.debug("Closing exchange connection socket")
            self._poller.unregister(self._connection)
            self._connection.close()
        logging.debug("Closing exchange server socket")
        self._poller.unregister(self._server_socket)
        self._server_socket.close()

    def _handle_activity(self, ready_list):
        for ready in ready_list:
            if not self._connection and ready[0] == self._server_socket.fileno():
                self._connection, self._connection_address = self._server_socket.accept()
                logging.info("Accepted exchange connection from %s" % repr(self._connection_address))
                self._poller.register(self._connection, select.POLLIN)
                self.send_packet_to_panel_drivers(packets.SimulationStart())
            elif self._connection and ready[0] == self._connection.fileno():
                if ready[1] & select.POLLHUP:
                    logging.info("Exchange connection %s hung up" % repr(self._connection_address))
                    self._poller.unregister(self._connection)
                    self.send_packet_to_panel_drivers(packets.SimulationStop())
                    self._connection = None
                    self._connection_address = None
                else:
                    payload = self._connection.recv(4096)
                    logging.debug("Exchange connection received %s byte(s)" % len(payload))
                    try:
                        self._parse_payload(payload.strip())
                    except Exception as e:
                        logging.error("failed to parse exchange payload: %s" % e.message)

    def _parse_payload(self, payload):
        logging.debug("Handling exchange connection payload '%s'" % payload)
        if payload.startswith("update "):
            data_tuples = payload[7:].split(",")
            for data_tuple in data_tuples:
                name, value = data_tuple.split("=")
                self.send_dataref_write(name, value)

    def _handle_panel_packet(self, packet):
        logging.debug("Exchange handling panel packet '%s'" % packet.__class__.__name__)
        if isinstance(packet, packets.DataSubscribeRequest):
            dataref = packet.get_dataref()
            if isinstance(dataref, DatarefInteger):
                data_type = "integer"
            elif isinstance(dataref, DatarefFloat):
                data_type = "float"
            elif isinstance(dataref, DatarefCommand):
                data_type = "command"
            else:
                raise NotImplementedError("exchange %s does not implement dataref type %s"
                                          % (self.__class__, dataref.__class__))
            payload = "register %s %s" % (dataref.get_name(), data_type)
        elif isinstance(packet, packets.DataWrite):
            dataref = packet.get_dataref()
            payload = "update %s %s" % (dataref.get_name(), dataref.get_value())
        elif isinstance(packet, packets.CommandBegin):
            command = packet.get_command()
            payload = "command %s begin" % (command.get_name())
        elif isinstance(packet, packets.CommandEnd):
            command = packet.get_command()
            payload = "command %s end" % (command.get_name())
        elif isinstance(packet, packets.CommandOnce):
            command = packet.get_command()
            payload = "command %s once" % (command.get_name())
        else:
            raise NotImplementedError("exchange %s does not implement packet of type %s"
                                      % (self.__class__, packet.__class__))
        self._connection.sendall(payload + "\n")
