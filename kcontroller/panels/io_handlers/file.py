from kcontroller.panels.io_handlers import IOHandler


class FileIOHandler(IOHandler):
    def __init__(self, filename):
        self._filename = filename
        self._last_checksum = None

    def poll(self):
        pass

    def recv(self):
        pass
