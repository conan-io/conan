from conans.util.log import logger
from conans.errors import ConanOutdatedClient
from conans.model.version import Version


class VersionCheckerRequester(object):

    def __init__(self, requester, client_version, min_server_compatible_version, out):

        assert(isinstance(client_version, Version))
        assert(isinstance(min_server_compatible_version, Version))
        self.requester = requester
        self.out = out
        self.client_version = client_version
        self.min_server_compatible_version = min_server_compatible_version

    def get(self, url, auth=None, headers=None, verify=None, stream=None):
        headers = headers or {}
        headers['X-Conan-Client-Version'] = str(self.client_version)
        ret = self.requester.get(url, auth=auth, headers=headers, verify=verify, stream=stream)
        self._handle_ret(ret)
        return ret

    def put(self, url, data, headers=None, verify=None, auth=None):
        headers = headers or {}
        headers['X-Conan-Client-Version'] = str(self.client_version)
        ret = self.requester.put(url, data=data, headers=headers, verify=verify, auth=auth)
        self._handle_ret(ret)
        return ret

    def delete(self, url, auth, headers, verify=None):
        headers = headers or {}
        headers['X-Conan-Client-Version'] = str(self.client_version)
        ret = self.requester.delete(url, auth=auth, headers=headers, verify=verify)
        self._handle_ret(ret)
        return ret

    def post(self, url, auth=None, headers=None, verify=None, stream=None, data=None, json=None):
        headers = headers or {}
        headers['X-Conan-Client-Version'] = str(self.client_version)
        ret = self.requester.post(url, auth=auth, headers=headers,
                                  verify=verify, stream=stream, data=data, json=json)
        self._handle_ret(ret)
        return ret

    def _handle_ret(self, ret):
        ret_version_status = ret.headers.get('X-Conan-Client-Version-Check', None)
        logger.debug("Remote version check result '%s' " % ret_version_status)
        if ret_version_status:
            server_version = ret.headers.get('X-Conan-Server-Version', None)
            server_version = Version(server_version)
            logger.debug("Remote version '%s' " % server_version)

            if ret_version_status == "current":
                return
            elif ret_version_status == "outdated":
                msg = "A new conan version (v%s) is available in current remote. " % server_version
                self.out.warn(msg + "Please, upgrade conan client to avoid deprecation.")
            elif ret_version_status == "deprecated":
                msg = "Your conan's client version is deprecated for the "\
                      "current remote (v%s). " % server_version
                # If we operate with a fixed remote (-r XXX) this exception will stop the execution
                # but if not, remote_manager will continue with the next remote ignoring this.
                raise ConanOutdatedClient(msg + "Upgrade conan client.")
            elif ret_version_status == "server_outdated":
                if server_version < self.min_server_compatible_version:
                    msg = "Your conan's client is incompatible with this remote." \
                          " The server is deprecated. (v%s). "\
                          "Please, contact with your system administrator" \
                          " and upgrade the server." % server_version
                    raise ConanOutdatedClient(msg)
