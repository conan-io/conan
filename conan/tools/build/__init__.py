import configparser
import os
import sys
from shlex import quote

from conan.tools.build.flags import cppstd_flag
from conan.tools.build.cppstd import check_max_cppstd, check_min_cppstd, \
    valid_max_cppstd, valid_min_cppstd, default_cppstd, supported_cppstd
from conan.tools.build.cstd import check_max_cstd, check_min_cstd, \
    valid_max_cstd, valid_min_cstd, supported_cstd
from conan.tools.build.cpu import build_jobs
from conan.tools.build.cross_building import cross_building, can_run
from conan.tools.build.stdcpp_library import stdcpp_library
from conan.errors import ConanException

CONAN_TOOLCHAIN_ARGS_FILE = "conanbuild.conf"
CONAN_TOOLCHAIN_ARGS_SECTION = "toolchain"


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


def load_toolchain_args(generators_folder=None, namespace=None):
    """
    Helper function to load the content of any CONAN_TOOLCHAIN_ARGS_FILE

    :param generators_folder: `str` folder where is located the CONAN_TOOLCHAIN_ARGS_FILE.
    :param namespace: `str` namespace to be prepended to the filename.
    :return: <class 'configparser.SectionProxy'>
    """
    namespace_name = "{}_{}".format(namespace, CONAN_TOOLCHAIN_ARGS_FILE) if namespace \
        else CONAN_TOOLCHAIN_ARGS_FILE
    args_file = os.path.join(generators_folder, namespace_name) if generators_folder \
        else namespace_name
    toolchain_config = configparser.ConfigParser()
    toolchain_file = toolchain_config.read(args_file)
    if not toolchain_file:
        raise ConanException("The file %s does not exist. Please, make sure that it was not"
                             " generated in another folder." % args_file)
    try:
        return toolchain_config[CONAN_TOOLCHAIN_ARGS_SECTION]
    except KeyError:
        raise ConanException("The primary section [%s] does not exist in the file %s. Please, add it"
                             " as the default one of all your configuration variables." %
                             (CONAN_TOOLCHAIN_ARGS_SECTION, args_file))


def save_toolchain_args(content, generators_folder=None, namespace=None):
    """
    Helper function to save the content into the CONAN_TOOLCHAIN_ARGS_FILE

    :param content: `dict` all the information to be saved into the toolchain file.
    :param namespace: `str` namespace to be prepended to the filename.
    :param generators_folder: `str` folder where is located the CONAN_TOOLCHAIN_ARGS_FILE
    """
    # Let's prune None values
    content_ = {k: v for k, v in content.items() if v is not None}
    namespace_name = "{}_{}".format(namespace, CONAN_TOOLCHAIN_ARGS_FILE) if namespace \
        else CONAN_TOOLCHAIN_ARGS_FILE
    args_file = os.path.join(generators_folder, namespace_name) if generators_folder \
        else namespace_name
    toolchain_config = configparser.ConfigParser()
    toolchain_config[CONAN_TOOLCHAIN_ARGS_SECTION] = content_
    with open(args_file, "w") as f:
        toolchain_config.write(f)
