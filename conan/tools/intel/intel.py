"""
    Intel generator module for Parallel Studio XE (legacy) and oneAPI integrations.

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

from conan.tools.env import Environment
from conans.client.tools.env import env_diff
from conans.client.tools.win import is_win64, _system_registry_key, MSVS_YEAR
from conans.errors import ConanException


def is_using_intel_oneapi(compiler_version):
    """Check if the Intel compiler to be used belongs to Intel oneAPI

    Note: Intel oneAPI Toolkit first version is 2021.1
    """
    return int(compiler_version.split(".")[0]) >= 2021


class Intel:

    filename = "conanintelvars"

    def __init__(self, conanfile, arch=None, force=False):
        self._conanfile = conanfile
        compiler_version = conanfile.settings.get_safe("compiler.version")
        mode = conanfile.settings.get_safe("compiler.mode")
        if is_using_intel_oneapi(compiler_version):
            if mode == "classic":
                self._interface = _InteloneAPIClassic(conanfile, arch=arch, force=force)
            elif conanfile.settings.get_safe("os") != "Darwin":
                self._interface = _InteloneAPIClang(conanfile, arch=arch, force=force)
            else:  # MacOS is not supported for the new oneAPI compilers
                raise ConanException(
                    'macOS* is not supported for the icx/icpx or dpcpp compilers. '
                    'Use the "classic" mode instead (icc compiler).')
        else:
            self._interface = _IntelLegacy(conanfile, arch=arch, force=force)

    @property
    def ms_toolset(self):
        return self._interface.ms_toolset

    @property
    def command(self):
        return self._interface.command

    def environment(self):
        env = Environment(conanfile=self._conanfile)
        for k, v in env_diff(self.command, True).items():
            env.append(k, v)
        return env

    def generate(self, env=None, auto_activate=False):
        env = env or self.environment()
        env.save_script(self.filename, auto_activate=auto_activate)


class _InteloneAPIBase:
    """Intel oneAPI base class"""

    def __init__(self, conanfile, arch=None, force=False):
        self._conanfile = conanfile
        self._settings = conanfile.settings
        self._arch = arch or conanfile.settings.get_safe("arch")
        self._compiler_version = conanfile.settings.get_safe("compiler.version")
        self._mode = conanfile.settings.get_safe("compiler.mode")
        self._force = force
        self._out = conanfile.output

    @property
    def installation_path(self):
        system = platform.system()

        installation_path = self._conanfile.conf["tools.intel:installation_path"]
        if not installation_path:
            # Let's try the default dirs
            if system == "Windows":
                if self._arch == "x86":
                    intel_arch = "IA32"
                elif self._arch == "x86_64":
                    intel_arch = "EM64T"
                else:
                    raise ConanException("don't know how to find Intel compiler on %s" % self._arch)
                if is_win64():
                    base = r"SOFTWARE\WOW6432Node"
                else:
                    base = r"SOFTWARE"
                intel_version = self._compiler_version if "." in self._compiler_version \
                    else self._compiler_version + ".0"
                base = r"{base}\Intel\Suites\{intel_version}".format(
                    base=base, intel_version=intel_version
                )
                from six.moves import winreg  # @UnresolvedImport
                path = base + r"\Defaults\C++\{arch}".format(arch=intel_arch)
                subkey = _system_registry_key(winreg.HKEY_LOCAL_MACHINE, path, "SubKey")
                if not subkey:
                    raise ConanException("unable to find Intel C++ compiler installation")
                path = base + r"\{subkey}\C++".format(subkey=subkey)
                installation_path = _system_registry_key(winreg.HKEY_LOCAL_MACHINE, path,
                                                         "LatestDir")
                if not installation_path:
                    raise ConanException("Don't know how to find Intel oneAPI folder on %s" % system)
            else:
                # If it was installed as root
                installation_path = os.path.join(os.sep, "opt", "intel", "oneapi")
                if not os.path.exists(installation_path):
                    # Try if it was installed as normal user
                    installation_path = os.path.join(os.path.expanduser("~"), "intel", "oneapi")
                if not os.path.exists(installation_path):
                    raise ConanException("Don't know how to find Intel oneAPI folder on %s" % system)

        self._out.info("Got Intel oneAPI installation folder: %s" % installation_path)
        return installation_path

    @property
    def command(self):
        """Get the setvars.bat/setvars.sh load command

        :return:
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
        # Add architecture argument
        if self._arch == "x86_64":
            command += " intel64"
        elif self._arch == "x86":
            command += " ia32"
        else:
            raise ConanException("don't know how to call %s for %s" % (svars, self._arch))
        # Add visual studio arguments
        compiler_base = self._settings.get_safe("compiler.base")
        if compiler_base == "Visual Studio":
            base_version = self._settings.get_safe("compiler.base.version")
            if base_version:
                command += " vs%s" % MSVS_YEAR.get(base_version)
        if self._force:
            command += " --force"
        return command


class _InteloneAPIClassic(_InteloneAPIBase):
    """Intel oneAPI C++ Compiler Classic """

    @property
    def ms_toolset(self):
        # TODO: hardcoded value but will it depend on the version?
        return "Intel C++ Compiler 19.2"


class _InteloneAPIClang(_InteloneAPIBase):
    """Intel oneAPI DPC++/C++ Compiler"""

    @property
    def ms_toolset(self):
        # By default, we'll assume you are using C/C++ mode else DPC++
        if self._mode == "dpcpp":  # DPC++
            return "Intel(R) oneAPI DPC++ Compiler"
        else:
            return "Intel C++ Compiler %s" % (self._compiler_version.split('.')[0])


class _IntelLegacy:
    """Old-fashioned Intel C++ Compiler also known as part of Intel Parallel Studio XE"""

    # https://software.intel.com/en-us/articles/intel-compiler-and-composer-update-version-numbers-to-compiler-version-number-mapping
    INTEL_YEAR = {"19.1": "2020",
                  "19": "2019",
                  "18": "2018",
                  "17": "2017",
                  "16": "2016",
                  "15": "2015"}

    def __init__(self, conanfile, arch=None, force=False):
        self._conanfile = conanfile
        self._settings = conanfile.settings
        self._version = conanfile.settings.get_safe("compiler.version")
        self._arch = arch or conanfile.settings.get_safe("arch")
        self._force = force
        self._out = conanfile.output

    @property
    def ms_toolset(self):
        compiler_version = self._settings.get_safe("compiler.version")
        if compiler_version:
            compiler_version = compiler_version if "." in compiler_version else \
                "%s.0" % compiler_version
            return "Intel C++ Compiler " + compiler_version

    @property
    def installation_path(self):
        installation_path = self._conanfile.conf["tools.intel:installation_path"]
        if installation_path:
            return installation_path

        system = platform.system()
        if system in ["Linux", "Darwin"]:
            subdir = "mac" if system == "Darwin" else "linux"
            year = _IntelLegacy.INTEL_YEAR.get(self._version)
            installation_path = os.path.join(os.sep, "opt", "intel",
                                             "compilers_and_libraries_%s" % year, subdir)
        elif system == "Windows":
            if self._arch == "x86":
                intel_arch = "IA32"
            elif self._arch == "x86_64":
                intel_arch = "EM64T"
            else:
                raise ConanException("don't know how to find Intel compiler on %s" % self._arch)
            if is_win64():
                base = r"SOFTWARE\WOW6432Node"
            else:
                base = r"SOFTWARE"
            intel_version = self._version if "." in self._version else self._version + ".0"
            base = r"{base}\Intel\Suites\{intel_version}".format(
                base=base, intel_version=intel_version
            )
            from six.moves import winreg  # @UnresolvedImport
            path = base + r"\Defaults\C++\{arch}".format(arch=intel_arch)
            subkey = _system_registry_key(winreg.HKEY_LOCAL_MACHINE, path, "SubKey")
            if not subkey:
                raise ConanException("unable to find Intel C++ compiler installation")
            path = base + r"\{subkey}\C++".format(subkey=subkey)
            installation_path = _system_registry_key(winreg.HKEY_LOCAL_MACHINE, path, "LatestDir")
            if not installation_path:
                raise ConanException("unable to find Intel C++ compiler installation")
        else:
            raise ConanException("don't know how to find Intel compiler on %s" % system)
        return installation_path

    @property
    def command(self):
        """Get the compilervars.bat/compilervars.sh load command

        https://software.intel.com/en-us/intel-system-studio-cplusplus-compiler-user-and-reference-guide-using-compilervars-file

        :return:
        """
        if "PSTLROOT" in os.environ and not self._force:
            return "echo Conan:intel_compilervars already set"

        system = platform.system()
        cvars = "compilervars.bat" if system == "Windows" else "compilervars.sh"
        command = os.path.join(self.installation_path, "bin", cvars)
        command = '"%s"' % command
        if system == "Windows":
            command = "call " + command
        else:
            command = ". " + command  # dot is more portable than source
        if self._arch == "x86_64":
            command += " -arch intel64"
            if system != "Windows":
                command = "COMPILERVARS_ARCHITECTURE=intel64 " + command
        elif self._arch == "x86":
            command += " -arch ia32"
            if system != "Windows":
                command = "COMPILERVARS_ARCHITECTURE=ia32 " + command
        else:
            raise ConanException("don't know how to call %s for %s" % (cvars, self._arch))
        if system == "Darwin":
            command += " -platform mac"
            command = "COMPILERVARS_PLATFORM=mac " + command
        elif system == "Linux":
            command += " -platform linux"
            command = "COMPILERVARS_PLATFORM=linux " + command
        elif system == "Windows":
            pass  # no -platform on Windows, intentionally
        else:
            raise ConanException("don't know how to call %s for %s" % (cvars, system))
        compiler_base = self._settings.get_safe("compiler.base")
        if compiler_base == "Visual Studio":
            base_version = self._settings.get_safe("compiler.base.version")
            if base_version:
                command += " vs%s" % MSVS_YEAR.get(base_version)
        if self._force:
            command += " --force"
        return command
