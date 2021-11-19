from bottle import Bottle

from conans.errors import EXCEPTION_CODE_MAPPING
from conans.server.rest.bottle_plugins.http_basic_authentication import HttpBasicAuthentication
from conans.server.rest.bottle_plugins.jwt_authentication import JWTAuthentication
from conans.server.rest.bottle_plugins.return_handler import ReturnHandlerPlugin
from conans.server.rest.controller.v2.ping import PingController
from conans.server.rest.controller.v2.users import UsersController
from conans.server.rest.controller.v2.conan import ConanControllerV2
from conans.server.rest.controller.v2.delete import DeleteControllerV2
from conans.server.rest.controller.v2.revisions import RevisionsController
from conans.server.rest.controller.v2.search import SearchControllerV2


class ApiV2(Bottle):

    def __init__(self, credentials_manager, server_capabilities):

        self.credentials_manager = credentials_manager
        self.server_capabilities = server_capabilities
        Bottle.__init__(self)

    def setup(self):
        self.install_plugins()

        # Capabilities in a ping
        PingController().attach_to(self)

        SearchControllerV2().attach_to(self)
        DeleteControllerV2().attach_to(self)
        ConanControllerV2().attach_to(self)
        RevisionsController().attach_to(self)

        # Install users controller
        UsersController().attach_to(self)

    def install_plugins(self):
        # Second, check Http Basic Auth
        self.install(HttpBasicAuthentication())

        # Map exceptions to http return codes
        self.install(ReturnHandlerPlugin(EXCEPTION_CODE_MAPPING))

        # Handle jwt auth
        self.install(JWTAuthentication(self.credentials_manager))
