import subprocess
import sys

from conans.model.version import Version

CONAN_TOOLCHAIN_ARGS_FILE = "conanbuild.conf"
CONAN_TOOLCHAIN_ARGS_SECTION = "toolchain"


def args_to_string(args):
    if not args:
        return ""
    # FIXME: This is ugly, hardcoding condition how to parse args
    if sys.platform == 'win32':
        return subprocess.list2cmdline(args)
    else:
        return " ".join("'" + arg.replace("'", r"'\''") + "'" for arg in args)
