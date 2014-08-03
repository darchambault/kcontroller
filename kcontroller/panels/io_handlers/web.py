import logging
from flask import Flask
from gunicorn.app.base import Application
from kcontroller.blueprints import dashboard
from kcontroller.controller import Controller


class KController(Application):
    def __init__(self):
        super(KController, self).__init__()
        self._controller = Controller()

    def init(self, parser, opts, args):
        pass

    def load(self):
        logging.info("starting worker")
        dashboard.controller = self._controller

        app = Flask("kcontroller", static_url_path='/static')
        app.debug = True
        app.register_blueprint(dashboard.dashboard, url_prefix='/dashboard')

        return app
