import logging
import struct
from kcontroller.panels.io_handlers import IOHandler, InputChange, OutputInstruction


class FileIOHandler(IOHandler):
    def __init__(self, in_filename, out_filename):
        self._in_filename = in_filename
        self._out_filename = out_filename
        self._previous_bytes = None
        open(self._in_filename, 'w').close()
        open(self._out_filename, 'w').close()
        logging.debug("listening on %s" % self._in_filename)
        logging.debug("writing to %s" % self._out_filename)

    def send(self, data):
        """
        Send output instructions

        :param data: list of OutputInstruction objects
        :type: list
        """
        instructions_by_size = _get_instructions_by_size(data)

        payloads = []
        for size in sorted(instructions_by_size, reverse=True):
            for output_instruction in instructions_by_size[size]:
                if not _find_payload_for_output_instruction(output_instruction, payloads):
                    payloads.append(_pack_output_instruction(output_instruction))

        for i, payload in enumerate(payloads):
            if len(payload) < 64:
                payloads[i] += "0" * (64 - len(payload))

        f = open(self._out_filename, 'a')
        for payload in payloads:
            f.write(payload+"\n")
        f.close()

    def recv(self):
        """
        Receive input changes - to be overridden in class implementations

        :return: list of InputChange objects
        :rtype: list
        """
        input_bytes = self._read_bytes()
        changes = self._detect_input_changes(input_bytes)
        if changes:
            logging.info("detected %s change(s)" % len(changes))
        return changes

    def _read_bytes(self):
        f = open(self._in_filename, 'r')
        line = ''.join(f.readline().strip().split())
        f.close()
        hex_bytes = [line[i:i + 2] for i in range(0, len(line), 2)]
        return [int(hex_byte, 16) for hex_byte in hex_bytes]

    def _detect_input_changes(self, input_bytes):
        changed_inputs = []
        for i, value in enumerate(input_bytes):
            if not self._previous_bytes or i >= len(self._previous_bytes) or value != self._previous_bytes[i]:
                changed_inputs.append(InputChange(i, value, self._previous_bytes[i] if i < len(self._previous_bytes) else None))
        self._previous_bytes = input_bytes
        return changed_inputs


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


def _pack_output_instruction(output_instruction):
    ret = "%0.2X" % output_instruction.output_id
    raw = struct.pack("!" + output_instruction.value, output_instruction.data_type)
    for i in raw:
        ret += "%0.2X" % ord(i)
    return ret


def _find_payload_for_output_instruction(output_instruction, payloads):
    size = struct.calcsize("!" + output_instruction[1])
    for i, payload in enumerate(payloads):
        if (len(payload) + size + 1) <= 64:
            payloads[i] += _pack_output_instruction(output_instruction)
            return True
    return False
