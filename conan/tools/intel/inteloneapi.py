"""
    Intel generator module for oneAPI Toolkits.

    For simplicity and clarity, Intel informally refers to some of the terms in this document,
    as listed below:

        - ICX - Intel oneAPI DPC++/C++ Compiler
        - ICC Classic - Intel C++ Compiler Classic
        - DPCPP - Intel oneAPI DPC++/C++ Compiler

    DPCPP is built upon ICX as the underlying C++ Compiler, therefore most of this information
    also applies to DPCPP.

    Intel oneAPI Toolkit (DPC++/C++ Compiler)
        - Versioning: https://software.intel.com/content/www/us/en/develop/articles/oneapi-toolkit-version-to-compiler-version-mapping.html
        - Compiler: https://software.intel.com/content/www/us/en/develop/documentation/oneapi-dpcpp-cpp-compiler-dev-guide-and-reference/top.html
"""
import os
import platform

import six

from conan.tools.env import Environment
from conans.client.tools.env import env_diff
from conans.client.tools.win import is_win64, _system_registry_key
from conans.errors import ConanException


def is_using_intel_oneapi(compiler_version):
    """Check if the Intel compiler to be used belongs to Intel oneAPI

    Note: Intel oneAPI Toolkit first version is 2021.1
    """
    return int(compiler_version.split(".")[0]) >= 2021


def get_inteloneapi_installation_path():
    system = platform.system()
    # Let's try the default dirs
    if system == "Windows":
        if is_win64():
            base = r"SOFTWARE\WOW6432Node"
        else:
            base = r"SOFTWARE"
        path = r"{base}\Intel\Products\IntelOneAPI".format(base=base)
        from six.moves import winreg  # @UnresolvedImport
        installation_path = _system_registry_key(winreg.HKEY_LOCAL_MACHINE, path,
                                                 "ProductDIr")
        if not installation_path:
            raise ConanException("unable to find Intel oneAPI folder "
                                 "installation from Windows registry: %s" % path)
    elif system in ("Linux", "Darwin"):
        # If it was installed as root
        installation_path = os.path.join(os.sep, "opt", "intel", "oneapi")
        if not os.path.exists(installation_path):
            # Try if it was installed as a normal user
            installation_path = os.path.join(os.path.expanduser("~"), "intel", "oneapi")
        if not os.path.exists(installation_path):
            raise ConanException("Don't know how to find Intel oneAPI folder on %s" % system)
    else:
        raise ConanException("Your system is not supported by Intel oneAPI compilers.")


class IntelOneAPI:
    """Intel oneAPI DPC++/C++/Classic Compilers"""

    filename = "conanintelsetvars"

    def __init__(self, conanfile, command_args=None, arch=None, force=False):
        compiler_version = conanfile.settings.get_safe("compiler.version")
        mode = conanfile.settings.get_safe("compiler.mode")
        if is_using_intel_oneapi(compiler_version):
            if mode != "classic" and conanfile.settings.get_safe("os") == "Darwin":
                raise ConanException(
                    'macOS* is not supported for the icx/icpx or dpcpp compilers. '
                    'Use the "classic" mode (icc compiler) instead.')
        else:
            # Do not support legacy versions
            raise ConanException("You have to use 'intel' compiler which is meant for legacy "
                                 "versions like Intel Parallel Studio XE.")

        self._conanfile = conanfile
        self._settings = conanfile.settings
        self._arch = arch or conanfile.settings.get_safe("arch")
        self._compiler_version = compiler_version
        self._mode = mode
        self._force = force
        self._out = conanfile.output
        self._command_args = command_args

    @property
    def ms_toolset(self):
        if self._mode == "classic":
            # TODO: Get automatically the classic compiler version
            return "Intel C++ Compiler 19.2"
        elif self._mode == "icx":
            return "Intel C++ Compiler %s" % (self._compiler_version.split('.')[0])
        else:  # DPC++ compiler
            return "Intel(R) oneAPI DPC++ Compiler"

    def environment(self):
        env = Environment(conanfile=self._conanfile)
        for k, v in env_diff(self.command, True).items():
            env.append(k, v)
        return env

    def generate(self, env=None, group="build"):
        env = env or self.environment()
        env.save_script(self.filename, group=group)

    @property
    def installation_path(self):
        installation_path = self._conanfile.conf["tools.intel:installation_path"] or \
                            get_inteloneapi_installation_path()
        self._out.info("Got Intel oneAPI installation folder: %s" % installation_path)
        return installation_path

    @property
    def command(self):
        """Get the setvars.bat|sh load command

        :return: `str`
        """
        if str(os.getenv("SETVARS_COMPLETED", "")) == "1" and not self._force:
            return "echo Conan:intel_setvars already set"

        system = platform.system()
        svars = "setvars.bat" if system == "Windows" else "setvars.sh"
        command = os.path.join(self.installation_path, svars)
        command = '"%s"' % command
        if system == "Windows":
            command = "call " + command
        else:
            command = ". " + command  # dot is more portable than source
        # If user has passed custom arguments
        if self._command_args:
            command += self._command_args if isinstance(self._command_args, six.string_types) \
                else ' '.join(self._command_args)
            return command
        # Add architecture argument
        if self._arch == "x86_64":
            command += " intel64"
        elif self._arch == "x86":
            command += " ia32"
        else:
            raise ConanException("don't know how to call %s for %s" % (svars, self._arch))
        if self._force:
            command += " --force"
        return command
