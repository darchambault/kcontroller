from Queue import Queue
import socket
import threading


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
