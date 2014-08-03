from kcontroller.panels import Panel


class MainControlPanel(Panel):
    def _exchange_available(self):
        self._subscribe_dataref("v.altitude")
