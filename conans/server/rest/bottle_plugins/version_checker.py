from bottle import request, response, HTTPResponse
from conans.util.log import logger
import traceback
from conans.model.version import Version


class VersionCheckerPlugin(object):
    ''' The VersionCheckerPlugin plugin checks version from client and
        sets a header in the response to indicate if its last version, old version or deprecated version'''

    name = 'VersionCheckerPlugin'
    api = 2

    def __init__(self, server_version, min_client_compatible_version, server_capabilities):
        assert(isinstance(server_version, Version))
        assert(isinstance(min_client_compatible_version, Version))
        self.server_version = server_version
        self.min_client_compatible_version = min_client_compatible_version
        self.server_capabilities = server_capabilities

    def setup(self, app):
        ''' Make sure that other installed plugins don't affect the same
            keyword argument.'''
        for other in app.plugins:
            if not isinstance(other, VersionCheckerPlugin):
                continue

    def apply(self, callback, _):
        '''Apply plugin'''
        def wrapper(*args, **kwargs):
            '''Capture possible exceptions to manage the return'''
            client_version = request.headers.get('X-Conan-Client-Version', None)
            try:
                ret = callback(*args, **kwargs)  # kwargs has :xxx variables from url
            except HTTPResponse as resp:
                self.fill_response(client_version, resp)
                return resp

            if isinstance(ret, HTTPResponse):
                self.fill_response(client_version, ret)
            else:
                self.fill_response(client_version, response)
            return ret
        return wrapper

    def fill_response(self, client_version, resp):
        try:
            if client_version is not None:
                client_version = Version(client_version)
                if client_version < self.min_client_compatible_version:
                    check = 'deprecated'
                elif client_version < self.server_version:
                    check = 'outdated'
                elif client_version == self.server_version:
                    check = 'current'
                elif client_version > self.server_version:
                    # Client won't complain unless client has a "min_server_compatible_version"
                    # higher than current CONAN_SERVER_VERSION (not planned in conan development)
                    check = 'server_outdated'
                resp.headers['X-Conan-Client-Version-Check'] = check

            resp.headers['X-Conan-Server-Version'] = str(self.server_version)
            # colon separated, future: "complex_search" etc
            resp.headers['X-Conan-Server-Capabilities'] = ",".join(self.server_capabilities)
        except Exception:
            logger.error(traceback.format_exc())
