import bottle
from conans.server.rest.api_v1 import ApiV1
from conans.model.version import Version


class ConanServer(object):
    """
        Server class. Instances api_v1 application and run it.
        Receives the store.

    """
    store = None
    root_app = None

    def __init__(self, run_port, credentials_manager,
                 updown_auth_manager, authorizer, authenticator,
                 file_manager, search_manager, server_version, min_client_compatible_version,
                 server_capabilities):

        assert(isinstance(server_version, Version))
        assert(isinstance(min_client_compatible_version, Version))

        server_capabilities = server_capabilities or []

        self.api_v1 = ApiV1(credentials_manager, updown_auth_manager,
                            server_version, min_client_compatible_version,
                            server_capabilities)

        self.root_app = bottle.Bottle()
        self.root_app.mount("/v1/", self.api_v1)
        self.run_port = run_port
        self.api_v1.search_manager = search_manager
        self.api_v1.authorizer = authorizer
        self.api_v1.authenticator = authenticator
        self.api_v1.file_manager = file_manager

        self.api_v1.setup()

    def run(self, **kwargs):
        port = kwargs.pop("port", self.run_port)
        debug_set = kwargs.pop("debug", False)
        host = kwargs.pop("host", "localhost")
        bottle.Bottle.run(self.root_app, host=host,
                          port=port, debug=debug_set, reloader=False)
