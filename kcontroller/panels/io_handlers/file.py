import logging
from kcontroller.panels.io_handlers import ByteIOHandler


class FileIOHandler(ByteIOHandler):
    def __init__(self, in_filename, out_filename):
        super(FileIOHandler, self).__init__(packet_size=64)
        self._in_filename = in_filename
        self._out_filename = out_filename
        open(self._in_filename, 'w').close()
        open(self._out_filename, 'w').close()
        logging.debug("listening on %s" % self._in_filename)
        logging.debug("writing to %s" % self._out_filename)

    def _recv_data(self, size):
        """
        Receives data

        :param size: size of data expected to be received, in bytes
        :type size: int
        :return: data read, in string form
        :rtype: str
        """
        f = open(self._in_filename, 'r')
        hex_string = ''.join(f.readline().strip().split())
        f.close()
        return ''.join([chr(int(hex_string[i:i + 2], 16)) for i in range(0, len(hex_string), 2)][:size])

    def _send_data(self, data):
        """
        Sends data

        :param data: data to be sent, in string form
        :type data: str
        """
        data_hex = ' '.join(["%0.2X" % c for c in data])
        f = open(self._out_filename, 'a')
        f.write(data_hex+"\n")
        f.close()
