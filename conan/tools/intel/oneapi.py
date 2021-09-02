import os
import platform
from contextlib import contextmanager

from conans.client.tools.env import environment_append, env_diff
from conans.client.tools.win import MSVS_YEAR
from conans.errors import ConanException
from conans.util.env_reader import get_env


def get_intel_installation_path(out):
    system = platform.system()

    if system == "Darwin":
        # Let's show WARNING for macOS
        out.warn("The macOS* operating system is not supported by the "
                 "Intel oneAPI DPC++/C++ Compiler")

    installation_path = get_env("CONAN_INTEL_INSTALLATION_PATH")
    if not installation_path:
        # Let's try the default dirs
        if system == ["Linux", "Darwin"]:
            installation_path = os.path.join(os.sep, "opt", "intel", "oneapi")
        elif system == "Windows":
            installation_path = "C:\\Program Files (x86)\\Intel\\oneAPI"
        elif installation_path:
            raise ConanException("Don't know how to find Intel compiler on %s" % system)

    out.info("Got Intel oneAPI installation folder: %s" % installation_path)
    return installation_path


def get_intel_setvars_command(conanfile, arch=None, force=False):
    """
    https://software.intel.com/en-us/intel-system-studio-cplusplus-compiler-user-and-reference-guide-using-compilervars-file
    :return:
    """
    if str(os.getenv("SETVARS_COMPLETED"), "") == "1" and not force:
        return "echo Conan:intel_setvars already set"

    out = conanfile.output
    settings = conanfile.settings
    arch = arch or settings.get_safe("arch")
    system = platform.system()
    svars = "setvars.bat" if system == "Windows" else "setvars.sh"
    command = os.path.join(get_intel_installation_path(out),
                           svars)
    command = '"%s"' % command
    if system == "Windows":
        command = "call " + command
    else:
        command = ". " + command  # dot is more portable than source
    # Add architecture argument
    if arch == "x86_64":
        command += " intel64"
    elif arch == "x86":
        command += " ia32"
    else:
        raise ConanException("don't know how to call %s for %s" % (svars, arch))
    # Add visual studio arguments
    compiler_base = settings.get_safe("compiler.base")
    if compiler_base == "Visual Studio":
        base_version = settings.get_safe("compiler.base.version")
        if base_version:
            command += " vs%s" % MSVS_YEAR.get(base_version)
    return command


def get_intel_setvars_dict(conanfile, arch=None, force=False, only_diff=True):
    cmd = get_intel_setvars_command(conanfile, arch, force)
    return env_diff(cmd, only_diff)


@contextmanager
def intel_setvars(*args, **kwargs):
    new_env = get_intel_setvars_dict(*args, **kwargs)
    with environment_append(new_env):
        yield
