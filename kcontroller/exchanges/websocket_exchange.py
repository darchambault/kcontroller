import json
import logging
from time import sleep
import select
from websocket import create_connection
from kcontroller import packets
from kcontroller.kprocess import KProcess


class WebSocketExchange(KProcess):
    def __init__(self, url):
        super(WebSocketExchange, self).__init__()
        self._url = url
        self._ws = None

    def run(self):
        logging.info("%s starting" % self.__class__.__name__)
        self._initialize_websocket()
        try:
            while True:
                read_connections, = select.select([self._connection, self._ws], [], [])[:1]
                for connection in read_connections:
                    if connection == self._connection:
                        self._receive_panel_packet()
                    else:
                        self._receive_websocket_data()
                sleep(0.05)
        except KeyboardInterrupt:
            logging.info("Received SIGINT signal, shutting down...")

    def _initialize_websocket(self):
        self._ws = create_connection(self._url)
        self._send_websocket_data({"rate": 200})
        self._connection.send(packets.ExchangeAvailable())

    def _receive_panel_packet(self):
        packet = self._connection.recv()
        if isinstance(packet, packets.Packet):
            logging.debug("received packet from panels: %s" % packet)
            if isinstance(packet, packets.DataSubscribeRequest):
                self._send_websocket_data({"+": [packet.get_dataref()]})
            elif isinstance(packet, packets.DataWrite):
                self._send_websocket_data({"run": ["%s[%s]" % (packet.get_dataref(), packet.get_value())]})
            elif isinstance(packet, packets.CommandStart):
                self._send_websocket_data({"run": [packet.get_command()]})
            elif isinstance(packet, packets.CommandEnd):
                # do nothing, since Telemachus does not support command duration
                pass
            else:
                logging.warning("packet type %s is unimplemented" % packet.__class__.__name__)
                logging.debug("unimplemented packet: %s" % (repr(packet)))

    def _receive_websocket_data(self):
        data = self._ws.recv()
        if data:
            logging.debug("received %s byte(s) from sim" % len(data))
            logging.debug("received: %s" % data)
            payload = json.loads(data)
            for key in payload:
                self._send_event(packets.DataUpdate(key, payload[key]))

    def _send_websocket_data(self, payload):
        data = json.dumps(payload, separators=(',', ':'))
        logging.debug("sending %s byte(s) to sim" % len(data))
        logging.debug("sending: %s" % data)
        self._ws.send(data)