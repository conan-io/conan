from bottle import Bottle
from conans.server.rest.bottle_plugins.http_basic_authentication import HttpBasicAuthentication
from conans.server.rest.bottle_plugins.jwt_authentication import JWTAuthentication
from conans.server.rest.bottle_plugins.return_handler import ReturnHandlerPlugin
from conans.errors import EXCEPTION_CODE_MAPPING
from conans.server.rest.controllers.conan_controller import ConanController
from conans.server.rest.controllers.users_controller import UsersController
from conans.server.rest.controllers.file_upload_download_controller import FileUploadDownloadController
from conans.server.rest.bottle_plugins.version_checker import VersionCheckerPlugin


class ApiV1(Bottle):

    def __init__(self, credentials_manager, updown_auth_manager,
                 server_version, min_client_compatible_version,
                 server_capabilities, *argc, **argv):

        self.credentials_manager = credentials_manager
        self.updown_auth_manager = updown_auth_manager
        self.server_version = server_version
        self.min_client_compatible_version = min_client_compatible_version
        self.server_capabilities = server_capabilities
        Bottle.__init__(self, *argc, **argv)

    def setup(self):
        self.install_plugins()
        # Install conans controller
        ConanController("/conans").attach_to(self)
        # Install users controller
        UsersController("/users").attach_to(self)
        # Install updown controller
        if self.updown_auth_manager:
            FileUploadDownloadController("/files").attach_to(self)

    def install_plugins(self):
        # Check client version
        self.install(VersionCheckerPlugin(self.server_version,
                                          self.min_client_compatible_version,
                                          self.server_capabilities))

        # Second, check Http Basic Auth
        self.install(HttpBasicAuthentication())

        # Map exceptions to http return codes
        self.install(ReturnHandlerPlugin(EXCEPTION_CODE_MAPPING))

        # Handle jwt auth
        self.install(JWTAuthentication(self.credentials_manager))
