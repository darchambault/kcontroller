

class IOHandler(object):
    TYPE_BOOL = '?'
    TYPE_BYTE_UNSIGNED = 'B'
    TYPE_BYTE_SIGNED = 'b'
    TYPE_INT_UNSIGNED = 'I'
    TYPE_INT_SIGNED = 'i'
    TYPE_DOUBLE = 'd'

    def send(self, data):
        """
        Send output instructions - to be overridden in class implementations

        :param data: list of OutputInstruction objects
        :type: list
        """
        pass

    def recv(self):
        """
        Receive input changes - to be overridden in class implementations

        :return: list of InputChange objects
        :rtype: list
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


class InputChange(object):
    def __init__(self, input_id, new_value, previous_value):
        """
        Constructor

        :param input_id: The input ID
        :type input_id: int
        :param new_value: The input's new value
        :type new_value: int
        :param previous_value: The output's previous value
        :type previous_value: int
        """
        self.input_id = input_id
        self.new_value = new_value
        self.previous_value = previous_value


class OutputInstruction(object):
    def __init__(self, output_id, value, data_type):
        """
        Constructor

        :param output_id: The output ID
        :type output_id: int
        :param value: The value to be sent to the output, must match data_type
        :type value: bool or int or float
        :param data_type: A struct.pack() type - supported types are: ?, B, b, I, i, d
        :type data_type: str
        """
        self.output_id = output_id
        self.value = value
        self.data_type = data_type
