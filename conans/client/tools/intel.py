import os
import platform
from contextlib import contextmanager

from conans.client.tools.env import environment_append, env_diff
from conans.client.tools.win import is_win64, _system_registry_key, MSVS_YEAR
from conans.errors import ConanException
from conans.util.env_reader import get_env


# https://software.intel.com/en-us/articles/intel-compiler-and-composer-update-version-numbers-to-compiler-version-number-mapping
INTEL_YEAR = {"19.1": "2020",
              "19": "2019",
              "18": "2018",
              "17": "2017",
              "16": "2016",
              "15": "2015"}


def intel_installation_path(version, arch):
    installation_path = get_env("CONAN_INTEL_INSTALLATION_PATH")
    if installation_path:
        return installation_path

    system = platform.system()
    if system in ["Linux", "Darwin"]:
        subdir = "mac" if system == "Darwin" else "linux"
        year = INTEL_YEAR.get(version)
        installation_path = os.path.join(os.sep, "opt", "intel",
                                         "compilers_and_libraries_%s" % year, subdir)
    elif system == "Windows":
        if arch == "x86":
            intel_arch = "IA32"
        elif arch == "x86_64":
            intel_arch = "EM64T"
        else:
            raise ConanException("don't know how to find Intel compiler on %s" % arch)
        if is_win64():
            base = r"SOFTWARE\WOW6432Node"
        else:
            base = r"SOFTWARE"
        intel_version = version if "." in version else version + ".0"
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


def intel_compilervars_command(conanfile, arch=None, compiler_version=None, force=False):
    """
    https://software.intel.com/en-us/intel-system-studio-cplusplus-compiler-user-and-reference-guide-using-compilervars-file
    :return:
    """
    if "PSTLROOT" in os.environ and not force:
        return "echo Conan:intel_compilervars already set"
    settings = conanfile.settings
    compiler_version = compiler_version or settings.get_safe("compiler.version")
    arch = arch or settings.get_safe("arch")
    system = platform.system()
    cvars = "compilervars.bat" if system == "Windows" else "compilervars.sh"
    command = os.path.join(intel_installation_path(version=compiler_version, arch=arch), "bin",
                           cvars)
    command = '"%s"' % command
    if system == "Windows":
        command = "call " + command
    else:
        command = ". " + command  # dot is more portable than source
    if arch == "x86_64":
        command += " -arch intel64"
        if system != "Windows":
            command = "COMPILERVARS_ARCHITECTURE=intel64 " + command
    elif arch == "x86":
        command += " -arch ia32"
        if system != "Windows":
            command = "COMPILERVARS_ARCHITECTURE=ia32 " + command
    else:
        raise ConanException("don't know how to call %s for %s" % (cvars, arch))
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
    compiler_base = settings.get_safe("compiler.base")
    if compiler_base == "Visual Studio":
        base_version = settings.get_safe("compiler.base.version")
        if base_version:
            command += " vs%s" % MSVS_YEAR.get(base_version)
    return command


def intel_compilervars_dict(conanfile, arch=None, compiler_version=None, force=False,
                            only_diff=True):
    cmd = intel_compilervars_command(conanfile, arch, compiler_version, force)
    return env_diff(cmd, only_diff)


@contextmanager
def intel_compilervars(*args, **kwargs):
    new_env = intel_compilervars_dict(*args, **kwargs)
    with environment_append(new_env):
        yield
