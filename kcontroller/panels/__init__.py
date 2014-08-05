import logging
from time import sleep
from kcontroller.kprocess import KProcessPool, KProcess
from kcontroller import packets


class Panel(KProcess):
    def __init__(self, io_handler):
        super(Panel, self).__init__()
        self._io_handler = io_handler
        self._dataref_subscriptions = {}

    def run(self):
        logging.info("%s starting" % self.__class__.__name__)
        try:
            while True:
                self._check_for_exchange_packets()
                changes = self._io_handler.recv()
                if changes:
                    self._handle_io_changes(changes)
                sleep(0.05)
        except KeyboardInterrupt:
            logging.info("Received SIGINT signal, shutting down...")

    def _check_for_exchange_packets(self):
        if self._connection.poll():
            packet = self._connection.recv()
            if isinstance(packet, packets.Packet):
                logging.debug("received %s packet from controller: %s" %
                              (packet.__class__.__name__, repr(packet)))
                self._handle_exchange_packet(packet)
            else:
                logging.warning("received unrecognized packet: %s" % packet.__class__.__name__)
                logging.debug("unrecognized packet: %s" % (repr(packet)))

    def _handle_exchange_packet(self, packet):
        if isinstance(packet, packets.DataUpdate):
            self._update_dataref(packet.get_dataref(), packet.get_value())
        elif isinstance(packet, packets.ExchangeAvailable):
            self._exchange_available()
        elif isinstance(packet, packets.ExchangeUnavailable):
            self._exchange_unavailable()
            self._dataref_subscriptions = {}
        else:
            logging.warning("packet type %s is unimplemented" % packet.__class__.__name__)
            logging.debug("unimplemented packet: %s" % (repr(packet)))

    def _subscribe_dataref(self, dataref):
        if dataref not in self._dataref_subscriptions:
            self._send_event(packets.DataSubscribeRequest(dataref))
            self._dataref_subscriptions[dataref] = None

    def _unsubscribe_dataref(self, dataref):
        if dataref in self._dataref_subscriptions:
            del self._dataref_subscriptions[dataref]

    def _update_dataref(self, dataref, value):
        if dataref in self._dataref_subscriptions:
            logging.debug("dataref update: %s => %s" % (dataref, value))
            self._dataref_subscriptions[dataref] = value
        else:
            logging.warning("received unexpected update for dataref %s" % dataref)

    def _handle_io_changes(self, changes):
        """
        Called on every main loop iteration with any/all input changes - to be overridden in class implementations

        :param changes: list of InputChange objects
        :type changes: list
        :return:
        """
        pass

    def _exchange_available(self):
        """
        Called when exchange becomes available - to be overridden in class implementations
        """
        pass

    def _exchange_unavailable(self):
        """
        Called when exchange becomes available - to be overridden in class implementations
        """
        pass


class PanelPool(KProcessPool):
    def __init__(self):
        super(PanelPool, self).__init__()
        self._panel_dataref_subscriptions = {}

    def broadcast(self, packet):
        if isinstance(packet, packets.DataUpdate):
            dataref = packet.get_dataref()
            if dataref in self._panel_dataref_subscriptions:
                for panel in self._panel_dataref_subscriptions[dataref]:
                    panel_connection = panel.get_parent_connection()
                    panel_connection.send(packet)
        else:
            if isinstance(packet, packets.ExchangeUnavailable):
                self._panel_dataref_subscriptions = {}
            for panel in self._kprocesses:
                panel_connection = panel.get_parent_connection()
                panel_connection.send(packet)

    def panel_packet_sent(self, packet, connection):
        panel = self._find_panel_from_connection(connection)
        if isinstance(packet, packets.DataSubscribeRequest):
            self._add_panel_dataref_subscription(packet.get_dataref(), panel)
        elif isinstance(packet, packets.DataUnsubscribeRequest):
            self._remove_panel_dataref_subscription(packet.get_dataref(), panel)

    def _add_panel_dataref_subscription(self, dataref, panel):
        if dataref not in self._panel_dataref_subscriptions:
            self._panel_dataref_subscriptions[dataref] = []
        self._panel_dataref_subscriptions[dataref].append(panel)

    def _remove_panel_dataref_subscription(self, dataref, panel):
        if dataref in self._panel_dataref_subscriptions:
            self._panel_dataref_subscriptions[dataref].remove(panel)

    def _find_panel_from_connection(self, connection):
        panel = None
        for panel in self._kprocesses:
            if panel.get_parent_connection() == connection:
                break
        if not panel:
            raise LookupError("could not find panel for connection %s" % connection)
        return panel
