import logging
import struct
from kcontroller.panels.io_handlers import IOHandler


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
        tuples_by_size = _get_tuples_by_size(data)

        payloads = []
        for size in sorted(tuples_by_size, reverse=True):
            for data_tuple in tuples_by_size[size]:
                if not _find_payload_for_tuple(data_tuple, payloads):
                    payloads.append(_pack_tuple(data_tuple))

        for i, payload in enumerate(payloads):
            if len(payload) < 64:
                payloads[i] += "0" * (64 - len(payload))

        f = open(self._out_filename, 'a')
        for payload in payloads:
            f.write(payload+"\n")
        f.close()

    def recv(self):
        input_bytes = self._read_bytes()
        changes = self._detect_changes(input_bytes)
        if changes:
            logging.info("detected %s change(s)" % len(changes))
        return changes

    def _read_bytes(self):
        f = open(self._in_filename, 'r')
        line = ''.join(f.readline().strip().split())
        f.close()
        hex_bytes = [line[i:i + 2] for i in range(0, len(line), 2)]
        return [int(hex_byte, 16) for hex_byte in hex_bytes]

    def _detect_changes(self, input_bytes):
        changed_bytes = []
        for i, value in enumerate(input_bytes):
            if not self._previous_bytes or i >= len(self._previous_bytes) or value != self._previous_bytes[i]:
                changed_bytes.append((i, value))
        self._previous_bytes = input_bytes
        return changed_bytes


def _get_tuples_by_size(data):
    tuples_by_size = {}
    for data_tuple in data:
        data_tuple_size = struct.calcsize("!" + data_tuple[1])
        if data_tuple_size not in tuples_by_size:
            tuples_by_size[data_tuple_size] = []
        tuples_by_size[data_tuple_size].append(data_tuple)
    return tuples_by_size


def _pack_tuple(data_tuple):
    ret = "%0.2X" % data_tuple[0]
    raw = struct.pack("!" + data_tuple[1], data_tuple[2])
    for i in raw:
        ret += "%0.2X" % ord(i)
    return ret


def _find_payload_for_tuple(data_tuple, payloads):
    size = struct.calcsize("!" + data_tuple[1])
    for i, payload in enumerate(payloads):
        if (len(payload) + size + 1) <= 64:
            payloads[i] += _pack_tuple(data_tuple)
            return True
    return False
