import TeensyRawhid
import usb.core


def print_packet(packet):
    out = ""
    for byte in packet:
        out += format(ord(byte), '02x').upper() + " "
    print out


class TeensyAdapter1(object):
    def __init__(self, vid=0x16c0, pid=0x0486):
        self._teensy = TeensyRawhid.Rawhid()
        self._vid = vid
        self._pid = pid

    def run(self):
        self._teensy.open(vid=self._vid, pid=self._pid)
        try:
            while True:
                packet = self._teensy.recv(64, 0)
                if len(packet):
                    print "Received valid %s byte(s) packet!" % len(packet)
                    print_packet(packet)
        except KeyboardInterrupt:
            pass
        self._teensy.close()


class TeensyAdapter2(object):
    def __init__(self, vid=0x16c0, pid=0x0486):
        self._vid = vid
        self._pid = pid
        self._interface = 0
        self._teensy = None

    def _init_teensy(self):
        self._teensy = usb.core.find(idVendor=self._vid, idProduct=self._pid)
        if self._teensy is None:
            raise EnvironmentError('Teensy device not found')
        if self._teensy.is_kernel_driver_active(self._interface) is True:
            print "but we need to detach kernel driver"
            self._teensy.detach_kernel_driver(self._interface)
            print "claiming device"
            usb.util.claim_interface(self._teensy, self._interface)

    def run(self):
        self._init_teensy()
        try:
            while True:
                packet = self._teensy.read(0x83, 64)
                if len(packet):
                    print "Received valid %s byte(s) packet!" % len(packet)
                    print_packet(packet)
        except KeyboardInterrupt:
            pass


def run():
    app = TeensyAdapter2()
    app.run()

if __name__ == "__main__":
    run()