import sys
from shlex import quote

from conan.tools.build.cppstd import check_max_cppstd, check_min_cppstd, \
    valid_max_cppstd, valid_min_cppstd, default_cppstd, supported_cppstd
from conan.tools.build.cpu import build_jobs
from conan.tools.build.cross_building import cross_building, can_run
from conan.tools.build.stdcpp_library import stdcpp_library


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


def cmd_args_to_string(args):
    if not args:
        return ""
    if sys.platform == 'win32':
        return _windows_cmd_args_to_string(args)
    else:
        return _unix_cmd_args_to_string(args)


def _unix_cmd_args_to_string(args):
    """Return a shell-escaped string from *split_command*."""
    return ' '.join(quote(arg) for arg in args)


def _windows_cmd_args_to_string(args):
    # FIXME: This is not managing all the parsing from list2cmdline, but covering simplified cases
    ret = []
    for arg in args:
        # escaped quotes have to escape the \ and then the ". Replace with <QUOTE> so next
        # replace doesn't interfere
        arg = arg.replace(r'\"', r'\\\<QUOTE>')
        # quotes have to be escaped
        arg = arg.replace(r'"', r'\"')

        # restore the quotes
        arg = arg.replace("<QUOTE>", '"')
        # if argument have spaces, quote it
        if ' ' in arg or '\t' in arg:
            ret.append('"{}"'.format(arg))
        else:
            ret.append(arg)
    return " ".join(ret)
