import TeensyRawhid
import pyusb;

class TeensyAdapter1(object):
    def __init__(self, vid=0x16c0, pid=0x0486):
        self._teensy = TeensyRawhid.Rawhid()
        self._vid = vid
        self._pid = pid

    def run(self):
        self._teensy.open(vid=self._vid, pid=self._pid)
        try:
            while 1:
                packet = self._teensy.recv(64, 0)
                if len(packet):
                    print "Received valid %s-byte packet!" % len(packet)
                    out = ""
                    for byte in packet:
                        out += format(ord(byte), '02x').upper() + " "
                    print out
        except KeyboardInterrupt:
            pass
        self._teensy.close()


class TeensyAdapter2(object):
    def __init__(self, vid=0x16c0, pid=0x0486):
        self._vid = vid
        self._pid = pid

    def run(self):
        pass


def run():
    app = TeensyAdapter2()
    app.run()

if __name__ == "__main__":
    run()