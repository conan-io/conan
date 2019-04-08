from bottle import Bottle

from conans.errors import EXCEPTION_CODE_MAPPING
from conans.server.rest.bottle_plugins.http_basic_authentication import HttpBasicAuthentication
from conans.server.rest.bottle_plugins.jwt_authentication import JWTAuthentication
from conans.server.rest.bottle_plugins.return_handler import ReturnHandlerPlugin
from conans.server.rest.controller.common.ping import PingController
from conans.server.rest.controller.common.users import UsersController
from conans.server.rest.controller.v1.conan import ConanController
from conans.server.rest.controller.v1.delete import DeleteController
from conans.server.rest.controller.v1.file_upload_download import \
    FileUploadDownloadController
from conans.server.rest.controller.v1.search import SearchController


class ApiV1(Bottle):

    def __init__(self, credentials_manager, updown_auth_manager,
                 server_capabilities, *argc, **argv):

        self.credentials_manager = credentials_manager
        self.updown_auth_manager = updown_auth_manager
        self.server_capabilities = server_capabilities
        Bottle.__init__(self, *argc, **argv)

    def setup(self):
        self.install_plugins()

        # Capabilities in a ping
        PingController().attach_to(self)

        # Install conans controller
        ConanController().attach_to(self)
        SearchController().attach_to(self)
        DeleteController().attach_to(self)

        # Install users controller
        UsersController().attach_to(self)

        # Install updown controller
        if self.updown_auth_manager:
            FileUploadDownloadController().attach_to(self)

    def install_plugins(self):
        # Second, check Http Basic Auth
        self.install(HttpBasicAuthentication())

        # Map exceptions to http return codes
        self.install(ReturnHandlerPlugin(EXCEPTION_CODE_MAPPING))

        # Handle jwt auth
        self.install(JWTAuthentication(self.credentials_manager))
