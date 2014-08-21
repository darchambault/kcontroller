import logging
import socket
import struct
import threading
import TeensyRawhid
import select
import time
from kcontroller import packets, PollableQueue
from kcontroller.dataref import Dataref, DatarefInteger, DatarefFloat
from kcontroller.panel_drivers import PanelDriver


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

        dataref = Dataref.factory(command, Dataref.COMMAND_BEGIN)
        packet = packets.CommandBegin(dataref)
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
