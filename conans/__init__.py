# Allow conans to import ConanFile from here
# to allow refactors
from conans.client.build.autotools_environment import AutoToolsBuildEnvironment
from conans.client.build.cmake import CMake
from conans.client.build.meson import Meson
from conans.client.build.msbuild import MSBuild
from conans.client.build.visual_environment import VisualStudioBuildEnvironment
from conans.client.run_environment import RunEnvironment
from conans.model.conan_file import ConanFile
from conans.model.options import Options
from conans.model.settings import Settings
from conans.util.files import load

# complex_search: With ORs and not filtering by not restricted settings
COMPLEX_SEARCH_CAPABILITY = "complex_search"
SERVER_CAPABILITIES = [COMPLEX_SEARCH_CAPABILITY, ]


<<<<<<< HEAD
__version__ = '1.1.0-dev'
=======
__version__ = '1.0.4'
>>>>>>> d0ffa809d0d05e76d74ebdc041f29dd4e13f4150
