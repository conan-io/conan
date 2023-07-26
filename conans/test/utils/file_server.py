import os
import uuid

import bottle
from webtest import TestApp

from conans.test.utils.test_files import temp_folder
from conans.util.files import mkdir


class TestFileServer:
    def __init__(self, store=None):
        self.store = store or temp_folder(path_with_spaces=False)
        mkdir(self.store)
        self.fake_url = "http://fake%s.com" % str(uuid.uuid4()).replace("-", "")
        self.root_app = bottle.Bottle()
        self.app = TestApp(self.root_app)
        self._attach_to(self.root_app, self.store)

    @staticmethod
    def _attach_to(app, store):
        @app.route("/<file>", method=["GET"])
        def get(file):
            return bottle.static_file(file, store)

        @app.route("/forbidden", method=["GET"])
        def get_forbidden():
            return bottle.HTTPError(403, "Access denied.")

        @app.route("/basic-auth/<file>", method=["GET"])
        def get_user_passwd(file):
            auth = bottle.request.auth
            if auth is not None:
                if auth != ("user", "passwd"):
                    return bottle.HTTPError(401, "Not authorized")
                return bottle.static_file(file, store)

            auth = bottle.request.headers.get("Authorization")
            if auth is None or auth != "Basic password":
                return bottle.HTTPError(401, "Not authorized")
            return bottle.static_file(file, store)

        @app.route("/internal_error", method=["GET"])
        def internal_error():
            return bottle.HTTPError(500, "Internal error")

        @app.route("/gz/<file>", method=["GET"])
        def get_gz(file):
            return bottle.static_file(file, store + "/gz", mimetype="application/octet-stream")

        @app.route("/<folder>/<file>", method=["GET"])
        def get_folder(folder, file):
            return bottle.static_file(file, os.path.join(store, folder))

    def __repr__(self):
        return "TestFileServer @ " + self.fake_url
