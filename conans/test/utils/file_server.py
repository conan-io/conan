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
            print("IAM HERE!!!!")
            return bottle.HTTPError(403, "Access denied.")

    def __repr__(self):
        return "TestFileServer @ " + self.fake_url
