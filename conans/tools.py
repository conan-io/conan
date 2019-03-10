"""
    Conan tools: classes and function in this module are intended to be used out of the box
    with the Conan configuration already currified into them. This configuration refers
    mainly to two items:
     - requester: on network calls, this will include proxy definition.
     - output: the output configuration

    Here in this module there should be no logic, all functions and classes must be implemented
    elsewhere (mainly in conans.util or conans.client.tools) and ready to be used without
    the currification.
"""

import requests

from conans.client.output import ConanOutput
# Tools from conans.client.tools
from conans.client.tools import files as tools_files, net as tools_net, oss as tools_oss, \
    system_pm as tools_system_pm, win as tools_win
from conans.client.tools.env import *  # pylint: disable=unused-import
from conans.client.tools.pkg_config import *  # pylint: disable=unused-import
from conans.client.tools.scm import *  # pylint: disable=unused-import
from conans.client.tools.apple import *
# Tools form conans.util
from conans.util.env_reader import get_env
from conans.util.files import _generic_algorithm_sum, load, md5, md5sum, mkdir, relative_dirs, \
    rmdir, save as files_save, save_append, sha1sum, sha256sum, touch, sha1sum, sha256sum, \
    to_file_bytes, touch
from conans.util.log import logger


# This global variables are intended to store the configuration of the running Conan application
_global_output = None
_global_requester = None


def set_global_instances(the_output, the_requester):
    global _global_output
    global _global_requester

    old_output, old_requester = _global_output, _global_requester

    # TODO: pass here the configuration file, and make the work here (explicit!)
    _global_output = the_output
    _global_requester = the_requester

    return old_output, old_requester


def get_global_instances():
    return _global_output, _global_requester


# Assign a default, will be overwritten in the factory of the ConanAPI
set_global_instances(the_output=ConanOutput(sys.stdout, True), the_requester=requests)


"""
From here onwards only currification is expected, no logic
"""


def save(path, content, append=False):
    # TODO: All this three functions: save, save_append and this one should be merged into one.
    if append:
        save_append(path=path, content=content)
    else:
        files_save(path=path, content=content, only_if_modified=False)


# From conans.client.tools.net
ftp_download = tools_net.ftp_download


def download(*args, **kwargs):
    return tools_net.download(out=_global_output, requester=_global_requester, *args, **kwargs)


def get(*args, **kwargs):
    return tools_net.get(output=_global_output, requester=_global_requester, *args, **kwargs)


# from conans.client.tools.files
chdir = tools_files.chdir
human_size = tools_files.human_size
untargz = tools_files.untargz
check_with_algorithm_sum = tools_files.check_with_algorithm_sum
check_sha1 = tools_files.check_sha1
check_md5 = tools_files.check_md5
check_sha256 = tools_files.check_sha256
patch = tools_files.patch
replace_prefix_in_pc_file = tools_files.replace_prefix_in_pc_file
collect_libs = tools_files.collect_libs
which = tools_files.which
unix2dos = tools_files.unix2dos
dos2unix = tools_files.dos2unix


def unzip(*args, **kwargs):
    return tools_files.unzip(output=_global_output, *args, **kwargs)


def replace_in_file(*args, **kwargs):
    return tools_files.replace_in_file(output=_global_output, *args, **kwargs)


def replace_path_in_file(*args, **kwargs):
    return tools_files.replace_path_in_file(output=_global_output, *args, **kwargs)


# from conans.client.tools.oss
args_to_string = tools_oss.args_to_string
detected_architecture = tools_oss.detected_architecture
OSInfo = tools_oss.OSInfo
cross_building = tools_oss.cross_building
get_cross_building_settings = tools_oss.get_cross_building_settings
get_gnu_triplet = tools_oss.get_gnu_triplet


def cpu_count(*args, **kwargs):
    return tools_oss.cpu_count(output=_global_output, *args, **kwargs)


# from conans.client.tools.system_pm
class SystemPackageTool(tools_system_pm.SystemPackageTool):
    def __init__(self, *args, **kwargs):
        super(SystemPackageTool, self).__init__(output=_global_output, *args, **kwargs)


class NullTool(tools_system_pm.NullTool):
    def __init__(self, *args, **kwargs):
        super(NullTool, self).__init__(output=_global_output, *args, **kwargs)


class AptTool(tools_system_pm.AptTool):
    def __init__(self, *args, **kwargs):
        super(AptTool, self).__init__(output=_global_output, *args, **kwargs)


class YumTool(tools_system_pm.YumTool):
    def __init__(self, *args, **kwargs):
        super(YumTool, self).__init__(output=_global_output, *args, **kwargs)


class BrewTool(tools_system_pm.BrewTool):
    def __init__(self, *args, **kwargs):
        super(BrewTool, self).__init__(output=_global_output, *args, **kwargs)


class PkgTool(tools_system_pm.PkgTool):
    def __init__(self, *args, **kwargs):
        super(PkgTool, self).__init__(output=_global_output, *args, **kwargs)


class ChocolateyTool(tools_system_pm.ChocolateyTool):
    def __init__(self, *args, **kwargs):
        super(ChocolateyTool, self).__init__(output=_global_output, *args, **kwargs)


class PkgUtilTool(tools_system_pm.PkgUtilTool):
    def __init__(self, *args, **kwargs):
        super(PkgUtilTool, self).__init__(output=_global_output, *args, **kwargs)


class PacManTool(tools_system_pm.PacManTool):
    def __init__(self, *args, **kwargs):
        super(PacManTool, self).__init__(output=_global_output, *args, **kwargs)


class ZypperTool(tools_system_pm.ZypperTool):
    def __init__(self, *args, **kwargs):
        super(ZypperTool, self).__init__(output=_global_output, *args, **kwargs)


# from conans.client.tools.win
vs_installation_path = tools_win.vs_installation_path
vswhere = tools_win.vswhere
vs_comntools = tools_win.vs_comntools
find_windows_10_sdk = tools_win.find_windows_10_sdk
escape_windows_cmd = tools_win.escape_windows_cmd
get_cased_path = tools_win.get_cased_path
MSYS2 = tools_win.MSYS2
MSYS = tools_win.MSYS
CYGWIN = tools_win.CYGWIN
WSL = tools_win.WSL
SFU = tools_win.SFU
unix_path = tools_win.unix_path
run_in_windows_bash = tools_win.run_in_windows_bash


@contextmanager
def vcvars(*args, **kwargs):
    with tools_win.vcvars(output=_global_output, *args, **kwargs):
        yield


def msvc_build_command(*args, **kwargs):
    return tools_win.msvc_build_command(output=_global_output, *args, **kwargs)


def build_sln_command(*args, **kwargs):
    return tools_win.build_sln_command(output=_global_output, *args, **kwargs)


def vcvars_command(*args, **kwargs):
    return tools_win.vcvars_command(output=_global_output, *args, **kwargs)


def vcvars_dict(*args, **kwargs):
    return tools_win.vcvars_dict(output=_global_output, *args, **kwargs)


def latest_vs_version_installed(*args, **kwargs):
    return tools_win.latest_vs_version_installed(output=_global_output, *args, **kwargs)


# Ready to use objects.
try:
    os_info = OSInfo()
except Exception as exc:
    logger.error(exc)
    _global_output.error("Error detecting os_info")
