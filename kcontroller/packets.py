

class Packet(object):
    pass


class CommandBegin(Packet):
    def __init__(self, command):
        self._command = command

    def get_command(self):
        return self._command

    def __str__(self):
        return "<%s %s>" % (self.__class__.__name__, self._command)


class CommandEnd(Packet):
    def __init__(self, command):
        self._command = command

    def get_command(self):
        return self._command

    def __str__(self):
        return "<%s %s>" % (self.__class__.__name__, self._command)


class CommandOnce(Packet):
    def __init__(self, command):
        self._command = command

    def get_command(self):
        return self._command

    def __str__(self):
        return "<%s %s>" % (self.__class__.__name__, self._command)


class DataWrite(Packet):
    def __init__(self, dataref):
        self._dataref = dataref

    def get_dataref(self):
        return self._dataref

    def __str__(self):
        return "<%s %s>" % (self.__class__.__name__, self._dataref)


class DataSubscribeRequest(Packet):
    def __init__(self, dataref):
        self._dataref = dataref

    def get_dataref(self):
        return self._dataref

    def __str__(self):
        return "<%s %s>" % (self.__class__.__name__, self._dataref)


class SimulationStart(Packet):
    def __str__(self):
        return "<%s>" % self.__class__.__name__


class SimulationStop(Packet):
    def __str__(self):
        return "<%s>" % self.__class__.__name__


class Shutdown(Packet):
    def __str__(self):
        return "<%s>" % self.__class__.__name__
