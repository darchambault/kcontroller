

class Packet(object):
    pass


class ExchangeAvailable(Packet):
    pass


class ExchangeUnavailable(Packet):
    pass


class CommandStart(Packet):
    def __init__(self, command):
        self._command = command

    def get_command(self):
        return self._command


class CommandEnd(Packet):
    def __init__(self, command):
        self._command = command

    def get_command(self):
        return self._command


class DataWrite(Packet):
    def __init__(self, dataref, value):
        self._dataref = dataref
        self._value = value

    def get_dataref(self):
        return self._dataref

    def get_value(self):
        return self._value


class DataSubscribeRequest(Packet):
    def __init__(self, dataref):
        self._dataref = dataref

    def get_dataref(self):
        return self._dataref


class DataUnsubscribeRequest(Packet):
    def __init__(self, dataref):
        self._dataref = dataref

    def get_dataref(self):
        return self._dataref


class DataUpdate(Packet):
    def __init__(self, dataref, value):
        self._dataref = dataref
        self._value = value

    def get_dataref(self):
        return self._dataref

    def get_value(self):
        return self._value
