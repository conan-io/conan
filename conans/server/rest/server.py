import bottle

from conans.server.rest.api_v2 import ApiV2


class ConanServer(object):
    """
        Server class. Instances api_v2 application and run it.
        Receives the store.

    """
    store = None
    root_app = None

    def __init__(self, run_port, credentials_manager,
                 updown_auth_manager, authorizer, authenticator,
                 server_store, server_capabilities):

        self.run_port = run_port

        server_capabilities = server_capabilities or []
        self.root_app = bottle.Bottle()

        self.api_v2 = ApiV2(credentials_manager, server_capabilities)
        self.api_v2.authorizer = authorizer
        self.api_v2.authenticator = authenticator
        self.api_v2.server_store = server_store
        self.api_v2.setup()
        self.root_app.mount("/v2/", self.api_v2)

    def run(self, **kwargs):
        port = kwargs.pop("port", self.run_port)
        debug_set = kwargs.pop("debug", False)
        host = kwargs.pop("host", "localhost")
        bottle.Bottle.run(self.root_app, host=host,
                          port=port, debug=debug_set, reloader=False)
