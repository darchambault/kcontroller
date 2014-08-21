import logging
import logging.config
import pkg_resources
from kcontroller import PollableQueue
from kcontroller.exchanges.kerbal_telemachus import KerbalTelemachusExchange
from kcontroller.exchanges.inet_socket import InetSocketExchange
from kcontroller.panel_drivers.inet_socket import InetSocketPanelDriver
from kcontroller.panel_drivers.teensy import TeensyPanelDriver


def _init_logging():
    logging_conf_file = pkg_resources.resource_filename("kcontroller", "resources/config/logging.cfg")
    logging.config.fileConfig(logging_conf_file, disable_existing_loggers=False)


def run():
    _init_logging()

    # drivers_to_load = [(TeensyPanelDriver, (), {"vid": 0x16c0, "pid": 0x0488})]
    drivers_to_load = [(InetSocketPanelDriver, (('', 1566), ), {})]
    # exchange_to_load = (KerbalTelemachusExchange, ("ws://192.168.1.100:8085/datalink", ), {})
    exchange_to_load = (InetSocketExchange, (('', 1565), ), {})

    panel_drivers = []
    for driver_to_load in drivers_to_load:
        logging.info("Starting panel driver %s" % driver_to_load[0].__name__)
        driver = driver_to_load[0](*driver_to_load[1], inbound_queue=PollableQueue(), outbound_queue=PollableQueue(),
                                   **driver_to_load[2])
        driver.start()
        panel_drivers.append(driver)

    exchange = exchange_to_load[0](panel_drivers=panel_drivers, *exchange_to_load[1], **exchange_to_load[2])
    exchange.run()


if __name__ == "__main__":
    run()
