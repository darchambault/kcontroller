import logging
import threading
import select
from kcontroller import packets


class PanelDriver(threading.Thread):
    def __init__(self, inbound_queue=None, outbound_queue=None):
        super(PanelDriver, self).__init__()

        self._inbound_queue = inbound_queue
        self._outbound_queue = outbound_queue
        self._poller = select.poll()
        self._poller.register(self._inbound_queue, select.POLLIN)

    def get_outbound_queue(self):
        return self._outbound_queue

    def get_inbound_queue(self):
        return self._inbound_queue

    def run(self):
        self._init()
        shutdown_requested = False

        while not shutdown_requested:
            ready_list = self._poller.poll()
            if len(ready_list):
                reduced_ready_list = []
                for ready in ready_list:
                    if ready[0] == self._inbound_queue.fileno():
                        packet = self._inbound_queue.get()
                        if isinstance(packet, packets.Shutdown):
                            shutdown_requested = True
                        else:
                            try:
                                self._handle_inbound_packet(packet)
                            except Exception as e:
                                logging.error("unable to handle inbound packet of type %s in %s: %s"
                                              % (packet.__class__, self.__class__, e.message))
                    else:
                        reduced_ready_list.append(ready)
                if len(reduced_ready_list):
                    self._handle_ready(reduced_ready_list)

        logging.debug("Shutting down panel driver %s" % self.__class__.__name__)
        self._finish()

    def send_packet_to_exchange(self, packet):
        logging.debug("Sending %s packet to exchange" % packet)
        self._outbound_queue.put(packet)

    def _init(self):
        pass

    def _finish(self):
        pass

    def _handle_ready(self, ready_list):
        pass

    def _handle_inbound_packet(self, packet):
        pass
