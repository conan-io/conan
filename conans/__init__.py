from collections import defaultdict

from conans.client.build.autotools_environment import AutoToolsBuildEnvironment
from conans.client.build.cmake import CMake
from conans.client.build.meson import Meson
from conans.client.build.msbuild import MSBuild
from conans.client.build.visual_environment import VisualStudioBuildEnvironment
from conans.client.run_environment import RunEnvironment
from conans.model.conan_file import ConanFile
from conans.model.options import Options
from conans.model.settings import Settings
from conans.model.env_info import Env
from conans.util.files import load


class ProfileOptions(defaultdict):

    def __init__(self):
        super(ProfileOptions, self).__init__(dict)

    def __getattr__(self, item):
        return self[item]

    def __setattr__(self, key, value):
        self[key] = value


class ProfileSettings(object):

    def __init__(self, value=None):
        self._value = value
        self._data = defaultdict(ProfileSettings)

    def value(self):
        if self._value:
            if not self._data:
                return self._value
            else:
                return {self._value: self.to_dict()}
        else:
            return self.to_dict()

    def __setattr__(self, key, value):
        if key not in ["_value", "_data"]:
            self._data[key] = ProfileSettings(value)
        else:
            super(ProfileSettings, self).__setattr__(key, value)

    def __getattr__(self, item):
        return self._data[item]

    def to_dict(self):
        return {key: item.value() for key, item in self._data.items()}


settings = ProfileSettings()
options = ProfileOptions()
env = ProfileOptions()


# complex_search: With ORs and not filtering by not restricted settings
COMPLEX_SEARCH_CAPABILITY = "complex_search"
CHECKSUM_DEPLOY = "checksum_deploy"  # Only when v2
REVISIONS = "revisions"  # Only when enabled in config, not by default look at server_launcher.py
ONLY_V2 = "only_v2"  # Remotes and virtuals from Artifactory returns this capability
MATRIX_PARAMS = "matrix_params"
OAUTH_TOKEN = "oauth_token"
SERVER_CAPABILITIES = [COMPLEX_SEARCH_CAPABILITY, REVISIONS]  # Server is always with revisions
DEFAULT_REVISION_V1 = "0"

__version__ = '1.34.0-dev'
