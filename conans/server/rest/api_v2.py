from bottle import Bottle

from conans.server.rest.api_v1 import ApiV1
from conans.server.rest.controllers.delete_controller import DeleteController
from conans.server.rest.controllers.ping_controller import PingController
from conans.server.rest.controllers.search_controller import SearchController
from conans.server.rest.controllers.users_controller import UsersController
from conans.server.rest.controllers.v2.conan_controller import ConanControllerV2


class ApiV2(ApiV1):

    def __init__(self, credentials_manager, server_version, min_client_compatible_version,
                 server_capabilities):

        self.credentials_manager = credentials_manager
        self.server_version = server_version
        self.min_client_compatible_version = min_client_compatible_version
        self.server_capabilities = server_capabilities
        Bottle.__init__(self)

    def setup(self):
        self.install_plugins()

        # Capabilities in a ping
        PingController("").attach_to(self)

        SearchController("/conans").attach_to(self)
        DeleteController("/conans").attach_to(self)
        ConanControllerV2("/conans").attach_to(self)

        # Install users controller
        UsersController("/users").attach_to(self)