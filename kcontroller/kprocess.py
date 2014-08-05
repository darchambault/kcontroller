from multiprocessing import Process, Pipe


class KProcess(Process):
    def __init__(self):
        super(KProcess, self).__init__()
        parent_conn, child_conn = Pipe()
        self._parent_connection = parent_conn
        self._connection = child_conn

    def get_parent_connection(self):
        return self._parent_connection

    def _send_event(self, event):
        self._connection.send(event)


class KProcessPool(object):
    def __init__(self):
        self._kprocesses = []

    def get_parent_connections(self):
        return [kprocess.get_parent_connection() for kprocess in self._kprocesses]

    def add(self, kprocess):
        self._kprocesses.append(kprocess)

    def start(self):
        for kprocess in self._kprocesses:
            kprocess.start()