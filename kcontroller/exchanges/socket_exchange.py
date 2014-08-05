import json
import logging
import socket
import select
from kcontroller.kprocess import KProcess
from kcontroller import packets


class SocketExchange(KProcess):
    def __init__(self, port, read_buffer_size=4096):
        super(SocketExchange, self).__init__()
        self._port = port
        self._server_socket = None
        self._socket_connection = None
        self._remote_addr = None
        self._read_buffer_size = read_buffer_size
        self._buffer = ""

    def run(self):
        logging.info("%s starting" % self.__class__.__name__)
        self._initialize_socket()
        try:
            while True:
                read_sockets, = select.select([self._server_socket], [], [])[:1]
                if read_sockets[0] == self._server_socket:
                    self._accept_socket()
                    while self._socket_connection:
                        read_sockets, = select.select([self._socket_connection, self._connection], [], [])[:1]
                        for sock in read_sockets:
                            try:
                                if sock == self._connection:
                                    self._receive_panel_packet()
                                else:
                                    try:
                                        self._receive_socket_data(sock)
                                    except ValueError as e:
                                        logging.warning("error parsing received JSON data: %s" % e.message)
                            except socket.error as e:
                                logging.warning("socket error %s: %s" % (e.__class__.__name__, e.message))
                                self._close_socket(sock)
        except KeyboardInterrupt:
            logging.info("Received SIGINT signal, shutting down...")

    def _initialize_socket(self):
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.bind(('', self._port))
        self._server_socket.listen(10)
        logging.info("listening for exchange connections on port %s" % self._port)

    def _accept_socket(self):
        connection_socket, addr = self._server_socket.accept()
        self._socket_connection = connection_socket
        self._remote_addr = addr
        logging.info("accepted socket connection from %s (port %s)" % (addr[0], addr[1]))
        self._connection.send(packets.ExchangeAvailable())

    def _close_socket(self, sock):
        sock.close()
        self._socket_connection = None
        self._connection.send(packets.ExchangeUnavailable())

    def _receive_panel_packet(self):
        packet = self._connection.recv()
        if isinstance(packet, packets.Packet):
            logging.debug("received packet from panels: %s" % packet)
            if isinstance(packet, packets.DataSubscribeRequest):
                self._send_socket_data({"+": [packet.get_dataref()]})
            elif isinstance(packet, packets.CommandStart):
                self._send_socket_data({"run": [packet.get_command()]})
            elif isinstance(packet, packets.CommandEnd):
                # do nothing, since Telemachus does not support command duration
                pass
            else:
                logging.warning("packet type %s is unimplemented" % packet.__class__.__name__)
                logging.debug("unimplemented packet: %s" % (repr(packet)))

    def _receive_socket_data(self, sock):
        try:
            data = sock.recv(self._read_buffer_size)
            if data:
                logging.debug("received %s byte(s) from sim" % len(data))
                payload = self._parse_socket_data(data)
                for key in payload:
                    self._send_event(packets.DataUpdate(key, payload[key]))
            else:
                logging.info("detected disconnected socket %s" % sock)
                self._close_socket(sock)
        except socket.error as e:
            logging.info("detected disconnected socket %s: %s" % (sock, e))
            self._close_socket(sock)

    def _parse_socket_data(self, data):
        self._buffer += data
        if "\n" in self._buffer:
            lines = self._buffer.split("\n", 2)
            self._buffer = lines[1]
            if lines[0]:
                return json.loads(lines[0])

    def _send_socket_data(self, payload):
        self._socket_connection.send(json.dumps(payload) + "\n")
