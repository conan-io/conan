# Allow conans to import ConanFile from here
# to allow refactors
import warnings

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


try:
    from conan.tools.gnu import MakeToolchain as _MakeToolchain
    from conans.client.output import Color, ConanOutput
    class MakeToolchain(_MakeToolchain):
        def __init__(self, conanfile, *args, **kwargs):
            msg = ("\n*****************************************************************\n"
                   "*****************************************************************\n"
                   "'from conans import MakeToolchain' has been deprecated and moved.\n"
                   "It will be removed in next Conan release.\n"
                   "Use 'from conan.tools.gnu import MakeToolchain' instead.\n"
                   "*****************************************************************\n"
                   "*****************************************************************\n")
            ConanOutput(conanfile.output._stream,
                        color=conanfile.output._color).writeln(msg, front=Color.BRIGHT_RED)
            warnings.warn(msg)
            super(MakeToolchain, self).__init__(conanfile, *args, **kwargs)
except ImportError:
    class MakeToolchain(object):
        def __init__(self, conanfile, *args, **kwargs):
            raise Exception("Python 2.7 is no longer supported for MakeToolchain")


try:
    from conan.tools.microsoft import MSBuildToolchain as _MSBuildToolchain
    from conans.client.output import Color, ConanOutput
    class MSBuildToolchain(_MSBuildToolchain):
        def __init__(self, conanfile, *args, **kwargs):
            msg = ("\n*****************************************************************\n"
                   "*****************************************************************\n"
                   "'from conans import MSBuildToolchain' has been deprecated and moved.\n"
                   "It will be removed in next Conan release.\n"
                   "Use 'from conan.tools.microsoft import MSBuildToolchain' instead.\n"
                   "*****************************************************************\n"
                   "*****************************************************************\n")
            ConanOutput(conanfile.output._stream,
                        color=conanfile.output._color).writeln(msg, front=Color.BRIGHT_RED)
            warnings.warn(msg)
            super(MSBuildToolchain, self).__init__(conanfile, *args, **kwargs)
except ImportError:
    class MSBuildToolchain(object):
        def __init__(self, conanfile, *args, **kwargs):
            raise Exception("Python 2.7 is no longer supported for MSBuildToolchain")


def CMakeToolchain(conanfile, **kwargs):
    # Warning
    msg = ("\n*****************************************************************\n"
           "*****************************************************************\n"
           "'from conans import CMakeToolchain' has been deprecated and moved.\n"
           "It will be removed in next Conan release.\n"
           "Use 'from conan.tools.cmake import CMakeToolchain' instead.\n"
           "*****************************************************************\n"
           "*****************************************************************\n")
    from conans.client.output import Color, ConanOutput
    ConanOutput(conanfile.output._stream,
                color=conanfile.output._color).writeln(msg, front=Color.BRIGHT_RED)
    warnings.warn(msg)
    try:
        from conan.tools.cmake import CMakeToolchain as _CMakeToolchain
        return _CMakeToolchain(conanfile, **kwargs)
    except ImportError:
        raise Exception("Python 2.7 is no longer supported for CMakeToolchain")


# complex_search: With ORs and not filtering by not restricted settings
COMPLEX_SEARCH_CAPABILITY = "complex_search"
CHECKSUM_DEPLOY = "checksum_deploy"  # Only when v2
REVISIONS = "revisions"  # Only when enabled in config, not by default look at server_launcher.py
ONLY_V2 = "only_v2"  # Remotes and virtuals from Artifactory returns this capability
MATRIX_PARAMS = "matrix_params"
OAUTH_TOKEN = "oauth_token"
SERVER_CAPABILITIES = [COMPLEX_SEARCH_CAPABILITY, REVISIONS]  # Server is always with revisions
DEFAULT_REVISION_V1 = "0"

__version__ = '1.32.0'
