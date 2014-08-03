

class IOHandler(object):
    def poll(self):
        """
        Poll for input - to be overridden in class implementations
        """
        pass

    def recv(self):
        """
        Receive input - to be overridden in class implementations
        """
        pass
