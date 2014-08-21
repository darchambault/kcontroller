import json
import logging
import select
from websocket import create_connection
from kcontroller import packets
from kcontroller.exchanges import Exchange


class KerbalTelemachusExchange(Exchange):
    __dataref_map = {
        "sim/cockpit/sas/actuators/toggle": "f.stage",
        "sim/cockpit/sas/state": "v.sasValue",
        "sim/cockpit/rcs/state": "v.rcsValue",
        }

    __key_map = dict((v, k) for k, v in __dataref_map.iteritems())

    def __init__(self, ws_url, *args, **kwargs):
        super(KerbalTelemachusExchange, self).__init__(*args, **kwargs)
        self._ws_url = ws_url
        self._ws = None

    def _init(self):
        self._ws = create_connection(self._ws_url)
        self._poller.register(self._ws, select.POLLIN)

    def _finish(self):
        self._poller.unregister(self._ws)
        self._ws.close()

    def _handle_activity(self, ready_list):
        for ready in ready_list:
            if ready[0] == self._ws.fileno():
                payload = self._ws.recv()
                if payload:
                    logging.debug("Exchange connection received %s byte(s)" % len(payload))
                    try:
                        self._parse_payload(payload.strip())
                    except Exception as e:
                        logging.error("failed to parse exchange payload: %s" % e.message)

    def _parse_payload(self, payload):
        logging.debug("Handling exchange connection payload '%s'" % payload)
        payload = json.loads(payload)
        for key in payload:
            dataref = self._get_dataref_for_key(key)
            if dataref:
                self.send_dataref_write(dataref, payload[key])

    def _handle_panel_packet(self, packet):
        logging.debug("Exchange handling panel packet '%s'" % packet.__class__.__name__)
        if isinstance(packet, packets.DataSubscribeRequest):
            key = self._get_key_for_dataref(packet.get_dataref().get_name())
            payload = {"+": [key]}
        elif isinstance(packet, packets.DataWrite):
            dataref = packet.get_dataref()
            payload = {"run": ["%s[%s]" % (dataref.get_name(), dataref.get_value())]}
        elif isinstance(packet, packets.CommandOnce) or isinstance(packet, packets.CommandBegin):
            command = packet.get_command()
            payload = {"run": [command.get_name()]}
        else:
            raise NotImplementedError("exchange %s does not implement packet of type %s"
                                      % (self.__class__, packet.__class__))
        self._ws.send(json.dumps(payload, separators=(',', ':')))

    @staticmethod
    def _get_dataref_for_key(key):
        if key in KerbalTelemachusExchange.__key_map:
            return KerbalTelemachusExchange.__key_map[key]
        return None

    @staticmethod
    def _get_key_for_dataref(name):
        if name in KerbalTelemachusExchange.__dataref_map:
            return KerbalTelemachusExchange.__dataref_map[name]
        return None
