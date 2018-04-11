
from conans.server.rest.api_v1 import ApiV1
from conans.server.rest.controllers.conan_controller_v2 import ConanControllerV2


class ApiV2(ApiV1):

    def setup(self):
        super(ApiV2, self).setup()
        ConanControllerV2("/conans").attach_to(self)

