import logging
from kcontroller import packets
from kcontroller.panels import Panel
from kcontroller.panels.io_handlers import OutputInstruction, IOHandler


class MainControlPanel(Panel):
    BUTTON_SAS_TOGGLE = 0
    BUTTON_STAGE = 1
    SWITCH_DUMP_TANK_1 = 2
    SWITCH_DUMP_TANK_2 = 3
    SWITCH_STAGING_ARMED = 4

    LED_STAGING_ARMED = 0
    LED_RCS = 1

    def __init__(self, io_handler):
        super(MainControlPanel, self).__init__(io_handler)
        self._staging_armed = False

    def _exchange_available(self):
        self._subscribe_dataref("v.rcsValue")

    def _handle_io_changes(self, changes):
        logging.debug("input changes received: %s" % changes)
        for change in changes:
            if change.input_id == self.BUTTON_SAS_TOGGLE and change.new_value:
                self._send_event(packets.CommandStart("f.sas"))
            elif change.input_id == self.SWITCH_STAGING_ARMED:
                # self._staging_armed = change.new_value == 1
                self._send_event(packets.DataWrite("f.rcs", "True" if change.new_value else "False"))
            elif change.input_id == self.BUTTON_STAGE and change.new_value and self._staging_armed:
                self._send_event(packets.CommandStart("f.stage"))

    def _update_device_outputs(self, data):
        output_instructions = [OutputInstruction(self.LED_STAGING_ARMED, self._staging_armed, IOHandler.TYPE_BOOL)]
        for dataref in data:
            if dataref == "v.rcsValue":
                output_instructions.append(OutputInstruction(self.LED_RCS, data[dataref] == "True", IOHandler.TYPE_BOOL))
        self._io_handler.send(output_instructions)
