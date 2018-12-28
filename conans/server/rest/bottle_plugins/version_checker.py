import traceback

from bottle import HTTPResponse, request, response

from conans.model.version import Version
from conans.util.log import logger


class VersionCheckerPlugin(object):
    ''' The VersionCheckerPlugin plugin checks version from client and
        sets a header in the response to indicate if its last version, old version or deprecated version'''

    name = 'VersionCheckerPlugin'
    api = 2

    def __init__(self, server_capabilities):
        self.server_capabilities = server_capabilities

    def setup(self, app):
        """ Make sure that other installed plugins don't affect the same
            keyword argument."""
        for other in app.plugins:
            if not isinstance(other, VersionCheckerPlugin):
                continue

    def apply(self, callback, _):
        """Apply plugin"""
        def wrapper(*args, **kwargs):
            """Capture possible exceptions to manage the return"""
            try:
                ret = callback(*args, **kwargs)  # kwargs has :xxx variables from url
            except HTTPResponse as resp:
                return resp

            if isinstance(ret, HTTPResponse):
                self.fill_response(ret)
            else:
                self.fill_response(response)  # TODO: response?
            return ret
        return wrapper

    def fill_response(self, resp):
        try:
            # colon separated, future: "complex_search" etc
            resp.headers['X-Conan-Server-Capabilities'] = ",".join(self.server_capabilities)
        except Exception:
            logger.error(traceback.format_exc())
