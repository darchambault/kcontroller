

class IOHandler(object):
    TYPE_BOOL = '?'
    TYPE_BYTE_UNSIGNED = 'B'
    TYPE_BYTE_SIGNED = 'b'
    TYPE_INT_UNSIGNED = 'I'
    TYPE_INT_SIGNED = 'i'
    TYPE_DOUBLE = 'd'

    def send(self, data):
        """
        Send ouput - to be overridden in class implementations
        """
        pass

    def recv(self):
        """
        Receive input - to be overridden in class implementations
        """
        pass

    @staticmethod
    def _is_valid_type(data_type):
        return data_type in [
            IOHandler.TYPE_BOOL,
            IOHandler.TYPE_BYTE_SIGNED,
            IOHandler.TYPE_BYTE_UNSIGNED,
            IOHandler.TYPE_INT_SIGNED,
            IOHandler.TYPE_INT_UNSIGNED,
            IOHandler.TYPE_DOUBLE,
        ]
