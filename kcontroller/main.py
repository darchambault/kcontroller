import os
import tempfile
import pkg_resources
import logging.config
import select

from kcontroller.exchanges.socket_exchange import SocketExchange
from kcontroller.panels import PanelPool
from kcontroller.panels.main_control_panel import MainControlPanel
from kcontroller.panels.io_handlers.file import FileIOHandler


def _init_logging():
    logging_conf_file = pkg_resources.resource_filename("kcontroller", "resources/config/logging.cfg")
    logging.config.fileConfig(logging_conf_file, disable_existing_loggers=False)


def run():
    _init_logging()
    logging.info("Starting up")

    panels = PanelPool()
    in_filename = os.path.join(tempfile.gettempdir(), "main_control_panel.in")
    out_filename = os.path.join(tempfile.gettempdir(), "main_control_panel.out")
    panels.add(MainControlPanel(FileIOHandler(in_filename, out_filename)))
    panels.start()

    exchange = SocketExchange(1414)
    exchange.start()
    exchange_connection = exchange.get_parent_connection()

    try:
        while True:
            panel_connections = panels.get_parent_connections()

            read_connections, = select.select(panel_connections + [exchange_connection], [], [])[:1]

            for connection in read_connections:
                packet = connection.recv()
                if connection == exchange_connection:
                    logging.debug("received packet from exchange: %s" % packet)
                    panels.broadcast(packet)
                else:
                    logging.debug("received packet from panels: %s" % packet)
                    panels.panel_packet_sent(packet, connection)
                    exchange_connection.send(packet)
    except KeyboardInterrupt:
        logging.info("Received SIGINT signal, shutting down...")


if __name__ == "__main__":
    run()
