import logging
from kcontroller.panels.io_handlers import ByteIOHandler
import TeensyRawhid


class TeensyHidIOHandler(ByteIOHandler):
    def __init__(self, vendor_id, product_id):
        super(TeensyHidIOHandler, self).__init__(packet_size=64)
        self._teensy = TeensyRawhid.Rawhid()
        self._teensy.open(vid=vendor_id, pid=product_id)
        logging.debug("found TeensyHID device!")

    def _recv_data(self, size):
        """
        Receives data

        :param size: size of data expected to be received, in bytes
        :type size: int
        :return: data read, in string form
        :rtype: str
        """
        self._teensy.recv(size, 1)

    def _send_data(self, data):
        """
        Sends data

        :param data: data to be sent, in string form
        :type data: str
        """
        self._teensy.send(data, len(data), 100)
