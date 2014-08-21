class Dataref(object):
    TYPE_COMMAND = 0
    TYPE_INTEGER = 1
    TYPE_FLOAT = 2

    COMMAND_BEGIN = 1
    COMMAND_END = 0
    COMMAND_ONCE = 2

    __dataref_types = {}

    @staticmethod
    def register(name, data_type):
        if name not in Dataref.__dataref_types:
            Dataref.__dataref_types[name] = data_type

    @staticmethod
    def factory(name, value):
        if name not in Dataref.__dataref_types:
            raise KeyError("dataref %s not registered" % name)

        dataref_type = Dataref.__dataref_types[name]

        if dataref_type == Dataref.TYPE_COMMAND:
            return DatarefCommand(name, value)
        elif dataref_type == Dataref.TYPE_INTEGER:
            return DatarefInteger(name, value)
        elif dataref_type == Dataref.TYPE_FLOAT:
            return DatarefFloat(name, value)

        raise NotImplementedError("unsupported dataref type %s" % dataref_type)

    def __init__(self, name, value):
        self._name = name
        self._value = value

    def get_name(self):
        return self._name

    def get_value(self):
        return self._value

    def __str__(self):
        return "<%s %s=%s>" % (self.__class__.__name__, self._name, self._value)


class DatarefCommand(Dataref):
    pass


class DatarefInteger(Dataref):
    def __init__(self, name, value):
        super(DatarefInteger, self).__init__(name, int(value) if value is not None else None)


class DatarefFloat(Dataref):
    def __init__(self, name, value):
        super(DatarefFloat, self).__init__(name, float(value) if value is not None else None)
