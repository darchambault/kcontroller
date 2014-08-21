from Queue import Queue
import TeensyRawhid
import json
import logging
import logging.config
import socket
import struct
import threading
import time
import pkg_resources
import select
from kcontroller import packets
from websocket import create_connection


class Dataref(object):
    TYPE_COMMAND = 0
    TYPE_INTEGER = 1
    TYPE_FLOAT = 2

    COMMAND_START = 1
    COMMAND_END = 0
    COMMAND_ONCE = 2

    __dataref_types = {}

    @staticmethod
    def register(name, data_type):
        if name not in Dataref.__dataref_types:
            Dataref.__dataref_types[name] = data_type

    @staticmethod
    def factory(name, value):
        if name not in Dataref.__dataref_types:
            raise KeyError("dataref %s not registered" % name)

        dataref_type = Dataref.__dataref_types[name]

        if dataref_type == Dataref.TYPE_COMMAND:
            return DatarefCommand(name, value)
        elif dataref_type == Dataref.TYPE_INTEGER:
            return DatarefInteger(name, value)
        elif dataref_type == Dataref.TYPE_FLOAT:
            return DatarefFloat(name, value)

        raise NotImplementedError("unsupported dataref type %s" % dataref_type)

    def __init__(self, name, value):
        self._name = name
        self._value = value

    def get_name(self):
        return self._name

    def get_value(self):
        return self._value

    def __str__(self):
        return "<%s %s=%s>" % (self.__class__.__name__, self._name, self._value)


class DatarefCommand(Dataref):
    pass


class DatarefInteger(Dataref):
    def __init__(self, name, value):
        super(DatarefInteger, self).__init__(name, int(value) if value is not None else None)


class DatarefFloat(Dataref):
    def __init__(self, name, value):
        super(DatarefFloat, self).__init__(name, float(value) if value is not None else None)


class PanelDriver(threading.Thread):
    def __init__(self, inbound_queue=None, outbound_queue=None):
        super(PanelDriver, self).__init__()

        self._inbound_queue = inbound_queue
        self._outbound_queue = outbound_queue
        self._poller = select.poll()
        self._poller.register(self._inbound_queue, select.POLLIN)

    def get_outbound_queue(self):
        return self._outbound_queue

    def get_inbound_queue(self):
        return self._inbound_queue

    def run(self):
        self._init()
        shutdown_requested = False

        while not shutdown_requested:
            ready_list = self._poller.poll()
            if len(ready_list):
                reduced_ready_list = []
                for ready in ready_list:
                    if ready[0] == self._inbound_queue.fileno():
                        packet = self._inbound_queue.get()
                        if isinstance(packet, packets.Shutdown):
                            shutdown_requested = True
                        else:
                            try:
                                self._handle_inbound_packet(packet)
                            except Exception as e:
                                logging.error("unable to handle inbound packet of type %s in %s: %s"
                                              % (packet.__class__, self.__class__, e.message))
                    else:
                        reduced_ready_list.append(ready)
                if len(reduced_ready_list):
                    self._handle_ready(reduced_ready_list)

        logging.debug("Shutting down panel driver %s" % self.__class__.__name__)
        self._finish()

    def send_packet_to_exchange(self, packet):
        logging.debug("Sending %s packet to exchange" % packet)
        self._outbound_queue.put(packet)

    def _init(self):
        pass

    def _finish(self):
        pass

    def _handle_ready(self, ready_list):
        pass

    def _handle_inbound_packet(self, packet):
        pass


class SocketPanelDriver(PanelDriver):
    def __init__(self, bind_address, *args, **kwargs):
        super(SocketPanelDriver, self).__init__(*args, **kwargs)
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
            if action == "start":
                dataref = Dataref.factory(name, Dataref.COMMAND_START)
                packet = packets.CommandStart(dataref)
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


class TeensyWrapper(threading.Thread):
    def __init__(self, shutdown_flag, sim_running_flag, vid=0x16c0, pid=0x0488, usage=0xa739, usage_page=0xff1c):
        super(TeensyWrapper, self).__init__()
        self._shutdown_flag = shutdown_flag
        self._sim_running_flag = sim_running_flag
        self._vid = vid
        self._pid = pid
        self._usage = usage
        self._usage_page = usage_page

        self.outbound_queue = PollableQueue()
        self.inbound_queue = PollableQueue()

        self._put_socket, self._get_socket = socket.socketpair()
        self._lock = threading.Lock()

    def run(self):
        logging.debug("Attempting to open device %s:%s" % (self._vid, self._pid))
        teensy = TeensyRawhid.Rawhid()
        teensy.open(vid=self._vid, pid=self._pid, usage=self._usage, usage_page=self._usage_page)

        last_keepalive = None
        poller = select.poll()
        poller.register(self.inbound_queue, select.POLLIN)

        while not self._shutdown_flag.is_set():
            if self._sim_running_flag.is_set():
                try:
                    payload = teensy.recv(64, 20)
                    logging.debug("received payload of %s byte(s) from teensy" % len(payload))
                    self.outbound_queue.put(payload)
                except IOError as e:
                    if e.errno is not None:
                        raise e

                ready_list = poller.poll(0.001)
                if len(ready_list):
                    payload = self.inbound_queue.get()
                    logging.debug("Teensy panel driver %s sending %s byte(s)"
                                  % (self.outbound_queue.fileno(), len(payload)))
                    teensy.send(payload, 100)

                now = time.time()
                if not last_keepalive or (now - last_keepalive) > 0.5:
                    teensy.send("\x04\x03\x02\x00", 100)
                    last_keepalive = now
            else:
                time.sleep(0.1)

        logging.debug("Closing device %s:%s" % (self._vid, self._pid))
        teensy.close()


class TeensyPanelDriver(PanelDriver):
    def __init__(self, vid=0x16c0, pid=0x0488, usage=0xa739, usage_page=0xff1c, *args, **kwargs):
        super(TeensyPanelDriver, self).__init__(*args, **kwargs)
        self._shutdown_flag = threading.Event()
        self._sim_running_flag = threading.Event()
        self._registration_map = {}
        self._teensy_wrapper = TeensyWrapper(self._shutdown_flag, self._sim_running_flag, vid=vid, pid=pid, usage=usage,
                                             usage_page=usage_page)

    def _init(self):
        self._registration_map = {}
        logging.debug("Starting teensy panel")
        self._teensy_wrapper.start()
        self._poller.register(self._teensy_wrapper.outbound_queue, select.POLLIN)

    def _finish(self):
        self._poller.unregister(self._teensy_wrapper.outbound_queue)
        logging.debug("Shutting down teensy panel")
        self._shutdown_flag.set()
        self._teensy_wrapper.join()

    def _handle_ready(self, ready_list):
        for ready in ready_list:
            if ready[0] == self._teensy_wrapper.outbound_queue.fileno():
                data = self._teensy_wrapper.outbound_queue.get()
                logging.debug("Teensy panel driver %s received %s byte(s)"
                              % (self._teensy_wrapper.outbound_queue.fileno(), len(data)))
                try:
                    received_payloads = TeensyPanelDriver._extract_payloads_from_buffer(data)
                    for payload in received_payloads:
                        logging.debug("Panel %s sent valid %s byte(s) packet!"
                                      % (self._teensy_wrapper.outbound_queue.fileno(), len(payload)))
                        self._parse_payload(payload)
                except Exception as e:
                    logging.warning("Teensy panel driver %s error: %s"
                                    % (self._teensy_wrapper.outbound_queue.fileno(), e.message))

    def _handle_inbound_packet(self, packet):
        logging.debug("Teensy panel driver %s received packet %s"
                      % (self._teensy_wrapper.outbound_queue.fileno(), packet))
        if isinstance(packet, packets.SimulationStart):
            payload = "\x04\x03\x01\x00"
            self._sim_running_flag.set()
        elif isinstance(packet, packets.SimulationStop):
            payload = "\x04\x03\x03\x00"
            self._sim_running_flag.clear()
        elif isinstance(packet, packets.DataWrite):
            payload = self._build_data_write_payload(packet.get_dataref())
        else:
            raise NotImplementedError("%s does not implement packet type %s" % (self.__class__, packet.__class__))
        self._teensy_wrapper.inbound_queue.put(payload)

    def _parse_payload(self, payload):
        packet_type = ord(payload[1])
        if packet_type == 0x01:
            self._parse_register_payload(payload)
        elif packet_type == 0x02:
            self._parse_write_payload(payload)
        elif packet_type == 0x04:
            self._parse_command_begin_payload(payload)
        elif packet_type == 0x05:
            self._parse_command_end_payload(payload)
        elif packet_type == 0x06:
            self._parse_command_once_payload(payload)

    def _parse_register_payload(self, payload):
        registration_type = ord(payload[4])
        if registration_type == 0x00:
            data_type = Dataref.TYPE_COMMAND
        elif registration_type == 0x01:
            data_type = Dataref.TYPE_INTEGER
        elif registration_type == 0x02:
            data_type = Dataref.TYPE_FLOAT
        else:
            raise IOError("unsupported registration type")

        registration_id = struct.unpack("<H", payload[2:4])[0]
        name = payload[6:]
        self._registration_map[registration_id] = name
        logging.info("Panel %s registered %s '%s' with id %s"
                     % (self._teensy_wrapper.outbound_queue.fileno(), data_type, name, registration_id))

        Dataref.register(name, data_type)
        dataref = Dataref.factory(name, None)
        packet = packets.DataSubscribeRequest(dataref)
        self.send_packet_to_exchange(packet)

    def _parse_write_payload(self, payload):
        data_type = ord(payload[4])
        if data_type == 0x01:
            value = struct.unpack("<i", payload[6:])
        elif data_type == 0x02:
            value = struct.unpack("<f", payload[6:])
        else:
            raise IOError("unsupported write data type")

        registration_id = struct.unpack("<H", payload[2:4])[0]
        name = self._registration_map[registration_id]
        logging.info("Panel %s wrote %s to %s"
                     % (self._teensy_wrapper.outbound_queue.fileno(), value, name))

        dataref = Dataref.factory(name, value)
        packet = packets.DataWrite(dataref)
        self.send_packet_to_exchange(packet)

    def _parse_command_begin_payload(self, payload):
        registration_id = struct.unpack("<H", payload[2:4])[0]
        command = self._registration_map[registration_id]
        logging.info("Panel %s began command for %s" % (self._teensy_wrapper.outbound_queue.fileno(), command))

        dataref = Dataref.factory(command, Dataref.COMMAND_START)
        packet = packets.CommandStart(dataref)
        self.send_packet_to_exchange(packet)

    def _parse_command_end_payload(self, payload):
        registration_id = struct.unpack("<H", payload[2:4])[0]
        command = self._registration_map[registration_id]
        logging.info("Panel %s ended command for %s" % (self._teensy_wrapper.outbound_queue.fileno(), command))

        dataref = Dataref.factory(command, Dataref.COMMAND_END)
        packet = packets.CommandEnd(dataref)
        self.send_packet_to_exchange(packet)

    def _parse_command_once_payload(self, payload):
        registration_id = struct.unpack("<H", payload[2:4])[0]
        command = self._registration_map[registration_id]
        logging.info("Panel %s activated command once for %s" % (self._teensy_wrapper.outbound_queue.fileno(), command))

        dataref = Dataref.factory(command, Dataref.COMMAND_ONCE)
        packet = packets.CommandOnce(dataref)
        self.send_packet_to_exchange(packet)

    @staticmethod
    def _extract_payloads_from_buffer(data):
        found_payloads = []
        payload_size = ord(data[0])
        while 1 < payload_size < len(data):
            found_payloads.append(data[0:payload_size])
            data = data[payload_size:]
            if len(data) > 0:
                payload_size = ord(data[0])
            else:
                payload_size = 0
        return found_payloads

    def _build_data_write_payload(self, dataref):
        if isinstance(dataref, DatarefInteger):
            data_type = 0x01
            symbol = "i"
        elif isinstance(dataref, DatarefFloat):
            data_type = 0x02
            symbol = "f"
        else:
            raise NotImplementedError("dataref type %s not implemented" % dataref.__class__.__name__)

        registration_id = None
        for map_id in self._registration_map:
            if self._registration_map[map_id] == dataref.get_name():
                registration_id = map_id
        if not registration_id:
            raise KeyError("could not find a dataref registration for %s" % dataref.get_name())

        return struct.pack("<BBHBB" + symbol, 10, 2, registration_id, data_type, 0, dataref.get_value())


class PollableQueue(Queue):
    def __init__(self, maxsize=0):
        Queue.__init__(self, maxsize=maxsize)
        self._put_socket, self._get_socket = socket.socketpair()
        self._lock = threading.Lock()

    def fileno(self):
        return self._get_socket.fileno()

    def put(self, item, block=True, timeout=None):
        with self._lock:
            Queue.put(self, item, block=block, timeout=timeout)
            self._put_socket.send(b'x')

    def get(self, block=True, timeout=None):
        with self._lock:
            self._get_socket.recv(1)
            return Queue.get(self, block=block, timeout=timeout)


class Exchange(object):
    def __init__(self, panel_drivers=None):
        self._panel_drivers = panel_drivers if panel_drivers else []

        self._poller = select.poll()

    def _get_panel_driver_queue_by_fileno(self, fileno):
        for panel_driver in self._panel_drivers:
            queue = panel_driver.get_outbound_queue()
            if fileno == queue.fileno():
                return queue
        return None

    def run(self):
        for panel_driver in self._panel_drivers:
            self._poller.register(panel_driver.get_outbound_queue(), select.POLLIN)
        self._init()
        try:
            while True:
                ready_list = self._poller.poll()
                if len(ready_list):
                    reduced_ready_list = []
                    for ready in ready_list:
                        panel_driver_queue = self._get_panel_driver_queue_by_fileno(ready[0])
                        if panel_driver_queue:
                            packet = panel_driver_queue.get()
                            try:
                                self._handle_panel_packet(packet)
                            except Exception as e:
                                logging.error("exchange failed to handle panel packet %s: %s"
                                              % (packet.__class__, e.message))
                        else:
                            reduced_ready_list.append(ready)
                    if len(reduced_ready_list):
                        self._handle_activity(reduced_ready_list)

        except KeyboardInterrupt:
            logging.info("Shutting down...")

            self.send_packet_to_panel_drivers(packets.Shutdown())

            for panel_driver in self._panel_drivers:
                panel_driver.join()

        logging.debug("Panel drivers shut down successfully")
        self._finish()
        logging.info("Shutdown successful")

    def send_dataref_write(self, name, value):
        try:
            dataref = Dataref.factory(name, value)
            self.send_packet_to_panel_drivers(packets.DataWrite(dataref))
        except KeyError:
            logging.warning("discarding unregistered dataref write for %s" % name)
        except NotImplementedError:
            logging.warning("discarding dataref write for %s because of unsupported type" % name)

    def send_packet_to_panel_drivers(self, packet):
        logging.debug("Sending %s packet to panel drivers" % packet)
        for panel_driver in self._panel_drivers:
            panel_driver.get_inbound_queue().put(packet)

    def _init(self):
        pass

    def _finish(self):
        pass

    def _handle_activity(self, ready_list):
        pass

    def _handle_panel_packet(self, packet):
        pass


class SocketExchange(Exchange):
    def __init__(self, bind_address, *args, **kwargs):
        super(SocketExchange, self).__init__(*args, **kwargs)
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
        elif isinstance(packet, packets.CommandStart):
            command = packet.get_command()
            payload = "command %s start" % (command.get_name())
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


class KerbalTelemachusExchange(Exchange):
    __dataref_map = {
        "sim/cockpit/sas/actuators/toggle": "f.stage",
        "sim/cockpit/sas/state": "v.sasValue",
        "sim/cockpit/rcs/state": "v.rcsValue",
    }

    __key_map = dict((v, k) for k, v in __dataref_map.iteritems())

    def __init__(self, ws_url, *args, **kwargs):
        super(KerbalTelemachusExchange, self).__init__(*args, **kwargs)
        self._ws_url = ws_url
        self._ws = None

    def _init(self):
        self._ws = create_connection(self._ws_url)
        self._poller.register(self._ws, select.POLLIN)

    def _finish(self):
        self._poller.unregister(self._ws)
        self._ws.close()

    def _handle_activity(self, ready_list):
        for ready in ready_list:
            if ready[0] == self._ws.fileno():
                payload = self._ws.recv()
                if payload:
                    logging.debug("Exchange connection received %s byte(s)" % len(payload))
                    try:
                        self._parse_payload(payload.strip())
                    except Exception as e:
                        logging.error("failed to parse exchange payload: %s" % e.message)

    def _parse_payload(self, payload):
        logging.debug("Handling exchange connection payload '%s'" % payload)
        payload = json.loads(payload)
        for key in payload:
            dataref = self._get_dataref_for_key(key)
            if dataref:
                self.send_dataref_write(dataref, payload[key])

    def _handle_panel_packet(self, packet):
        logging.debug("Exchange handling panel packet '%s'" % packet.__class__.__name__)
        if isinstance(packet, packets.DataSubscribeRequest):
            key = self._get_key_for_dataref(packet.get_dataref().get_name())
            payload = {"+": [key]}
        elif isinstance(packet, packets.DataWrite):
            dataref = packet.get_dataref()
            payload = {"run": ["%s[%s]" % (dataref.get_name(), dataref.get_value())]}
        elif isinstance(packet, packets.CommandOnce) or isinstance(packet, packets.CommandStart):
            command = packet.get_command()
            payload = {"run": [command.get_name()]}
        else:
            raise NotImplementedError("exchange %s does not implement packet of type %s"
                                      % (self.__class__, packet.__class__))
        self._ws.send(json.dumps(payload, separators=(',', ':')))

    @staticmethod
    def _get_dataref_for_key(key):
        if key in KerbalTelemachusExchange.__key_map:
            return KerbalTelemachusExchange.__key_map[key]
        return None

    @staticmethod
    def _get_key_for_dataref(name):
        if name in KerbalTelemachusExchange.__dataref_map:
            return KerbalTelemachusExchange.__dataref_map[name]
        return None


def _init_logging():
    logging_conf_file = pkg_resources.resource_filename("kcontroller", "resources/config/logging.cfg")
    logging.config.fileConfig(logging_conf_file, disable_existing_loggers=False)


def run():
    _init_logging()

    drivers_to_load = [(TeensyPanelDriver, (), {"vid": 0x16c0, "pid": 0x0488})]
    # drivers_to_load = [(SocketPanelDriver, (('', 1566), ), {})]
    # exchange_to_load = (KerbalTelemachusExchange, ("ws://192.168.1.100:8085/datalink", ), {})
    exchange_to_load = (SocketExchange, (('', 1565), ), {})

    panel_drivers = []
    for driver_to_load in drivers_to_load:
        logging.info("Starting panel driver %s" % driver_to_load[0].__name__)
        driver = driver_to_load[0](*driver_to_load[1], inbound_queue=PollableQueue(), outbound_queue=PollableQueue(),
                                   **driver_to_load[2])
        driver.start()
        panel_drivers.append(driver)

    exchange = exchange_to_load[0](panel_drivers=panel_drivers, *exchange_to_load[1], **exchange_to_load[2])
    exchange.run()


if __name__ == "__main__":
    run()
