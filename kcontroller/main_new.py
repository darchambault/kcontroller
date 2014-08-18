from Queue import Queue
import TeensyRawhid
import logging
import logging.config
import struct
from threading import Thread
import threading
import time
import pkg_resources
from kcontroller import packets


class TeensyAdapter(Thread):
    def __init__(self, vid=0x16c0, pid=0x0488, usage=0xa739, usage_page=0xff1c, run_event=None, sim_event=None,
                 device_queue=None, exchange_queue=None):
        super(TeensyAdapter, self).__init__()

        self._vid = vid
        self._pid = pid
        self._usage = usage
        self._usage_page = usage_page
        self._run_event = run_event
        self._sim_event = sim_event
        self._device_queue = device_queue
        self._exchange_queue = exchange_queue

        self._teensy = TeensyRawhid.Rawhid()
        self._last_keepalive = None
        self._registration_map = {}

    def get_input_queue(self):
        return self._device_queue

    def run(self):
        while self._run_event.is_set():
            if self._sim_event.is_set():
                self._registration_map = {}
                logging.info("Attempting to open device %s:%s" % (self._vid, self._pid))
                self._teensy.open(vid=self._vid, pid=self._pid, usage=self._usage, usage_page=self._usage_page)

                logging.debug("Sending enable/request IDs packet to %s:%s" % (self._vid, self._pid))
                self._teensy.send("\x04\x03\x01\x00", 100)

                logging.info("Sim activated for %s:%s" % (self._vid, self._pid))

                logging.debug("Starting main loop for %s:%s" % (self._vid, self._pid))
                while self._run_event.is_set() and self._sim_event.is_set():
                    try:
                        payload = self._teensy.recv(64, 20)
                        # self._print_packet(payload)
                        received_packets = self._extract_packets_from_buffer(payload)
                        for packet in received_packets:
                            logging.debug(
                                "Panel %s:%s sent valid %s byte(s) packet!" % (self._vid, self._pid, len(packet)))
                            self._parse_packet(packet)
                    except IOError as e:
                        if e.errno is not None:
                            raise e
                    self._keepalive()

                logging.debug("Sending disabled packet to %s:%s" % (self._vid, self._pid))
                self._teensy.send("\x04\x03\x03\x00", 100)

                logging.debug("Closing device %s:%s" % (self._vid, self._pid))
                self._teensy.close()

                logging.info("Sim deactivated for %s:%s" % (self._vid, self._pid))

    @staticmethod
    def _extract_packets_from_buffer(payload):
        found_packets = []
        packet_size = ord(payload[0])
        while 1 < packet_size < len(payload):
            found_packets.append(payload[0:packet_size])
            payload = payload[packet_size:]
            if len(payload) > 0:
                packet_size = ord(payload[0])
            else:
                packet_size = 0
        return found_packets

    def _parse_packet(self, packet):
        # self._print_packet(packet)
        packet_type = ord(packet[1])
        if packet_type == 0x01:
            self._parse_register_packet(packet)
        elif packet_type == 0x02:
            self._parse_write_packet(packet)
        elif packet_type == 0x04:
            self._parse_command_begin_packet(packet)
        elif packet_type == 0x05:
            self._parse_command_end_packet(packet)
        elif packet_type == 0x06:
            self._parse_command_once_packet(packet)

    def _parse_register_packet(self, packet):
        registration_type = ord(packet[4])
        if registration_type == 0x00:
            registration_type_str = "command"
        elif registration_type == 0x01:
            registration_type_str = "integer dataref"
        elif registration_type == 0x02:
            registration_type_str = "float dataref"
        else:
            raise IOError("unsupported registration type")

        registration_id = struct.unpack("<H", packet[2:4])[0]
        registration_name = packet[6:]
        logging.info("Panel %s:%s registered %s '%s' with id %s" % (
            self._vid, self._pid, registration_type_str, registration_name, registration_id))
        self._exchange_queue.put(packets.DataSubscribeRequest(registration_name))
        self._registration_map[registration_id] = registration_name

    def _parse_write_packet(self, packet):
        data_type = ord(packet[4])
        if data_type == 0x01:
            data_type = "integer dataref"
            data_value = struct.unpack("<i", packet[6:])
        elif data_type == 0x02:
            data_type = "float dataref"
            data_value = struct.unpack("<f", packet[6:])
        else:
            raise IOError("unsupported write data type")

        registration_id = struct.unpack("<H", packet[2:4])[0]
        dataref = self._registration_map[registration_id]
        logging.info(
            "Panel %s:%s wrote %s '%s' to %s" % (self._vid, self._pid, data_type, data_value, dataref))
        self._exchange_queue.put(packets.DataWrite(dataref, data_value))

    def _parse_command_begin_packet(self, packet):
        registration_id = struct.unpack("<H", packet[2:4])[0]
        command = self._registration_map[registration_id]
        logging.info("Panel %s:%s began command for %s" % (self._vid, self._pid, command))
        self._exchange_queue.put(packets.CommandStart(command))

    def _parse_command_end_packet(self, packet):
        registration_id = struct.unpack("<H", packet[2:4])[0]
        command = self._registration_map[registration_id]
        logging.info("Panel %s:%s ended command for %s" % (self._vid, self._pid, command))
        self._exchange_queue.put(packets.CommandEnd(command))

    def _parse_command_once_packet(self, packet):
        registration_id = struct.unpack("<H", packet[2:4])[0]
        command = self._registration_map[registration_id]
        logging.info("Panel %s:%s activated command once for %s" % (self._vid, self._pid, command))
        self._exchange_queue.put(packets.CommandOnce(command))

    def _keepalive(self):
        now = time.time()
        if not self._last_keepalive or (now - self._last_keepalive) > 0.5:
            self._teensy.send("\x04\x03\x02\x00", 100)
            self._last_keepalive = now

    @staticmethod
    def _print_packet(packet):
        out = ""
        for byte in packet:
            out += format(ord(byte), '02x').upper() + " "
        logging.debug(out)


class Exchange(Thread):
    def __init__(self, exchange_queue=None, run_event=None, sim_event=None, devices=[]):
        super(Exchange, self).__init__()
        self._exchange_queue = exchange_queue
        self._run_event = run_event
        self._sim_event = sim_event
        self._devices = devices

    def run(self):
        pass


class KerbalTelemachusExchange(Exchange):
    def __init__(self, address="ws://localhost:8085/datalink", **kwargs):
        super(KerbalTelemachusExchange, self).__init__(**kwargs)
        self._address = address

    def run(self):
        #TODO: implement actual interface with Kerbal Telemachus mod
        self._sim_event.set()


def _init_logging():
    logging_conf_file = pkg_resources.resource_filename("kcontroller", "resources/config/logging.cfg")
    logging.config.fileConfig(logging_conf_file, disable_existing_loggers=False)


def run():
    _init_logging()

    devices_to_load = [(0x16c0, 0x0488, TeensyAdapter)]
    exchange_class = KerbalTelemachusExchange
    exchange_args = {
        "address": "ws://192.168.1.100:8085/datalink"
    }

    run_event = threading.Event()
    run_event.set()

    sim_event = threading.Event()

    exchange_queue = Queue(maxsize=0)

    devices = []
    for device_to_load in devices_to_load:
        logging.info("Starting %s for %s:%s..." % (device_to_load[2].__name__, device_to_load[0], device_to_load[1]))
        device = device_to_load[2](vid=device_to_load[0], pid=device_to_load[1], run_event=run_event,
                                   sim_event=sim_event, device_queue=Queue(maxsize=0), exchange_queue=exchange_queue)
        device.start()
        devices.append(device)

    exchange = exchange_class(exchange_queue=exchange_queue, run_event=run_event, sim_event=sim_event, devices=devices,
                              **exchange_args)
    exchange.start()

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        logging.info("Shutting down...")
        run_event.clear()
        for device in devices:
            device.join()
        exchange.join()

    logging.info("Shutdown successful")


if __name__ == "__main__":
    run()