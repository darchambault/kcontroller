import logging
from kcontroller.panels import Panel


class MainControlPanel(Panel):
    BUTTON_SAS_TOGGLE = 0
    BUTTON_STAGE = 1
    SWITCH_DUMP_TANK_1 = 2
    SWITCH_DUMP_TANK_2 = 3
    SWITCH_STAGING_ARMED = 4

    def _exchange_available(self):
        self._subscribe_dataref("f.sas")

    def _handle_io_changes(self, changes):
        #TODO: implement IO changes handling in MainControlPanel
        logging.debug("input changes received: %s" % changes)