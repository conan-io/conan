from bottle import Bottle

from conans.server.rest.api_v1 import ApiV1
from conans.server.rest.controller.common.ping import PingController
from conans.server.rest.controller.common.users import UsersController
from conans.server.rest.controller.v2.conan import ConanControllerV2
from conans.server.rest.controller.v2.delete import DeleteControllerV2
from conans.server.rest.controller.v2.revisions import RevisionsController
from conans.server.rest.controller.v2.search import SearchControllerV2


class ApiV2(ApiV1):

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
