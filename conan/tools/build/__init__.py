import subprocess
import sys

from conan.tools.build.cpu import build_jobs
from conan.tools.build.cross_building import cross_building
from conan.tools.build.cppstd import check_min_cppstd, valid_min_cppstd


def use_win_mingw(conanfile):
    os_build = conanfile.settings_build.get_safe('os')
    if os_build == "Windows":
        compiler = conanfile.settings.get_safe("compiler")
        sub = conanfile.settings.get_safe("os.subsystem")
        if sub in ("cygwin", "msys2", "msys") or compiler == "qcc":
            return False
        else:
            return True
    return False


def args_to_string(args):
    if not args:
        return ""
    # FIXME: This is ugly, hardcoding condition how to parse args
    if sys.platform == 'win32':
        return subprocess.list2cmdline(args)
    else:
        return " ".join("'" + arg.replace("'", r"'\''") + "'" for arg in args)
