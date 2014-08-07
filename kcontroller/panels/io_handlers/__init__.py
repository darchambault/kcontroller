import logging
import struct


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


class ByteIOHandler(IOHandler):
    def __init__(self, packet_size=64):
        self._packet_size = packet_size
        self._previous_values = None

    def send(self, data):
        """
        Send output instructions

        :param data: list of OutputInstruction objects
        :type: list
        """
        instructions_by_size = self.__class__._get_instructions_by_size(data)

        payloads = []
        for size in sorted(instructions_by_size, reverse=True):
            for output_instruction in instructions_by_size[size]:
                if not self._add_output_instruction_to_available_payload(output_instruction, payloads):
                    payloads.append(self.__class__._pack_output_instruction(output_instruction))

        for i, payload in enumerate(payloads):
            if len(payload) < self._packet_size:
                payloads[i] += "\x00" * (self._packet_size - len(payload))

        for payload in payloads:
            self._send_data(payload)

    def recv(self):
        """
        Receive input changes

        :return: list of InputChange objects
        :rtype: list
        """
        packet = self._recv_data(self._packet_size)
        changes = self._detect_input_changes(packet)
        if changes:
            logging.info("detected %s change(s)" % len(changes))
        return changes

    def _recv_data(self, size):
        """
        Receives data - to be overridden in class implementation

        :param size: size of data expected to be received, in bytes
        :type size: int
        :return: data read, in string form
        :rtype: str
        """
        pass

    def _send_data(self, data):
        """
        Sends data - to be overridden in class implementation

        :param data: data to be sent, in string form
        :type data: str
        """
        pass

    def _detect_input_changes(self, packet):
        changed_inputs = []
        for i, value in enumerate(packet):
            if not self._previous_values or i >= len(self._previous_values) or value != self._previous_values[i]:
                previous_value = ord(self._previous_values[i]) if i < len(self._previous_values) else None
                changed_inputs.append(InputChange(i, ord(value), previous_value))
        self._previous_values = packet
        return changed_inputs

    def _add_output_instruction_to_available_payload(self, output_instruction, payloads):
        size = struct.calcsize("!" + output_instruction.data_type)
        for i, payload in enumerate(payloads):
            if (len(payload) + size + 1) <= self._packet_size:
                payloads[i] += self.__class__._pack_output_instruction(output_instruction)
                return True
        return False

    @staticmethod
    def _get_instructions_by_size(data):
        instructions_by_size = {}
        for output_instruction in data:
            if not isinstance(output_instruction, OutputInstruction):
                raise TypeError("can only send OutputInstruction objects")
            data_size = struct.calcsize("!" + output_instruction.data_type)
            if data_size not in instructions_by_size:
                instructions_by_size[data_size] = []
            instructions_by_size[data_size].append(output_instruction)
        return instructions_by_size

    @staticmethod
    def _pack_output_instruction(output_instruction):
        pack_format = "!B" + output_instruction.data_type
        return struct.pack(pack_format, output_instruction.output_id, output_instruction.value)


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
