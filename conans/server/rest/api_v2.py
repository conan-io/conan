from conans.server.rest.api_v1 import ApiV1
from conans.server.rest.controllers.conan_controller_v2 import ConanControllerV2
from conans.server.rest.controllers.users_controller import UsersController
from conans.server.rest.controllers.file_upload_download_controller import FileUploadDownloadController


class ApiV2(ApiV1):

    def __init__(self, *argc, **argv):
        ApiV1.__init__(self, *argc, **argv)

    def setup(self):
        self.install_plugins()
        # Install conans controller
        ConanControllerV2("/conans").attach_to(self)
        # Install users controller
        UsersController("/users").attach_to(self)
        # Install updown controller
        if self.updown_auth_manager:
            FileUploadDownloadController("/files").attach_to(self)
