import logging
import select
from kcontroller import packets
from kcontroller.dataref import Dataref


class Exchange(object):
    def __init__(self, panel_drivers=None):
        self._panel_drivers = panel_drivers if panel_drivers else []

        self._poller = select.poll()

    def _get_panel_driver_queue_by_fileno(self, fileno):
        for panel_driver in self._panel_drivers:
            queue = panel_driver.get_outbound_queue()
            if fileno == queue.fileno():
                return queue
        return None

    def run(self):
        for panel_driver in self._panel_drivers:
            self._poller.register(panel_driver.get_outbound_queue(), select.POLLIN)
        self._init()
        try:
            while True:
                ready_list = self._poller.poll()
                if len(ready_list):
                    reduced_ready_list = []
                    for ready in ready_list:
                        panel_driver_queue = self._get_panel_driver_queue_by_fileno(ready[0])
                        if panel_driver_queue:
                            packet = panel_driver_queue.get()
                            try:
                                self._handle_panel_packet(packet)
                            except Exception as e:
                                logging.error("exchange failed to handle panel packet %s: %s"
                                              % (packet.__class__, e.message))
                        else:
                            reduced_ready_list.append(ready)
                    if len(reduced_ready_list):
                        self._handle_activity(reduced_ready_list)

        except KeyboardInterrupt:
            logging.info("Shutting down...")

            self.send_packet_to_panel_drivers(packets.Shutdown())

            for panel_driver in self._panel_drivers:
                panel_driver.join()

        logging.debug("Panel drivers shut down successfully")
        self._finish()
        logging.info("Shutdown successful")

    def send_dataref_write(self, name, value):
        try:
            dataref = Dataref.factory(name, value)
            self.send_packet_to_panel_drivers(packets.DataWrite(dataref))
        except KeyError:
            logging.warning("discarding unregistered dataref write for %s" % name)
        except NotImplementedError:
            logging.warning("discarding dataref write for %s because of unsupported type" % name)

    def send_packet_to_panel_drivers(self, packet):
        logging.debug("Sending %s packet to panel drivers" % packet)
        for panel_driver in self._panel_drivers:
            panel_driver.get_inbound_queue().put(packet)

    def _init(self):
        pass

    def _finish(self):
        pass

    def _handle_activity(self, ready_list):
        pass

    def _handle_panel_packet(self, packet):
        pass
