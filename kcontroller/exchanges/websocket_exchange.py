import logging
from time import sleep
from websocket import create_connection
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
                self._ws.recv()
                self._check_for_packets()
                sleep(0.05)
        except KeyboardInterrupt:
            logging.info("Received SIGINT signal, shutting down...")

    def _initialize_websocket(self):
        self._ws = create_connection(self._url)
