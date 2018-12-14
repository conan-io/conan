from bottle import Bottle

from conans.server.rest.api_v1 import ApiV1
from conans.server.rest.controllers.ping_controller import PingController
from conans.server.rest.controllers.users_controller import UsersController
from conans.server.rest.controllers.v2.conan_controller import ConanControllerV2
from conans.server.rest.controllers.v2.delete_controller import DeleteControllerV2
from conans.server.rest.controllers.v2.search_controller import SearchControllerV2


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

        SearchControllerV2("/conans").attach_to(self)
        DeleteControllerV2("/conans").attach_to(self)
        ConanControllerV2("/conans").attach_to(self)

        # Install users controller
        UsersController("/users").attach_to(self)
