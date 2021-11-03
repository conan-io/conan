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

from conans.cli.output import ConanOutput
# Tools from conans.client.tools
from conans.client.tools import files as tools_files, oss as tools_oss, \
    system_pm as tools_system_pm
from conans.client.tools.env import *  # pylint: disable=unused-import
from conans.client.tools.pkg_config import *  # pylint: disable=unused-import
from conans.client.tools.scm import *  # pylint: disable=unused-import
from conans.client.tools.settings import *  # pylint: disable=unused-import
from conans.client.tools.apple import *
# Tools form conans.util
from conans.util.env_reader import get_env
from conans.util.files import _generic_algorithm_sum, load, md5, md5sum, mkdir, relative_dirs, \
    rmdir, save as files_save, save_append, sha1sum, sha256sum, to_file_bytes, touch
from conans.util.log import logger
from conans.client.tools.version import Version
from conans.client.build.cppstd_flags import cppstd_flag_new as cppstd_flag  # pylint: disable=unused-import


# This global variables are intended to store the configuration of the running Conan application
_global_requester = None
_global_config = None


def set_global_instances(the_requester, config):
    global _global_requester
    global _global_config

    # TODO: pass here the configuration file, and make the work here (explicit!)
    _global_requester = the_requester
    _global_config = config


# Assign a default, will be overwritten in the factory of the ConanAPI
set_global_instances(the_requester=requests, config=None)


"""
From here onwards only currification is expected, no logic
"""


def save(path, content, append=False):
    # TODO: All this three functions: save, save_append and this one should be merged into one.
    if append:
        save_append(path=path, content=content)
    else:
        files_save(path=path, content=content, only_if_modified=False)


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
rename = tools_files.rename
fix_symlinks = tools_files.fix_symlinks
remove_files_by_mask = tools_files.remove_files_by_mask


def unzip(*args, **kwargs):
    return tools_files.unzip(*args, **kwargs)


def replace_in_file(*args, **kwargs):
    return tools_files.replace_in_file(*args, **kwargs)


def replace_path_in_file(*args, **kwargs):
    return tools_files.replace_path_in_file(*args, **kwargs)


# from conans.client.tools.oss
args_to_string = tools_oss.args_to_string
OSInfo = tools_oss.OSInfo
cross_building = tools_oss.cross_building
get_cross_building_settings = tools_oss.get_cross_building_settings
get_gnu_triplet = tools_oss.get_gnu_triplet


def cpu_count(*args, **kwargs):
    return tools_oss.cpu_count(*args, **kwargs)


# from conans.client.tools.system_pm
class SystemPackageTool(tools_system_pm.SystemPackageTool):
    def __init__(self, *args, **kwargs):
        super(SystemPackageTool, self).__init__(*args, **kwargs)


class NullTool(tools_system_pm.NullTool):
    def __init__(self, *args, **kwargs):
        super(NullTool, self).__init__(*args, **kwargs)


class AptTool(tools_system_pm.AptTool):
    def __init__(self, *args, **kwargs):
        super(AptTool, self).__init__(*args, **kwargs)


class DnfTool(tools_system_pm.DnfTool):
    def __init__(self, *args, **kwargs):
        super(DnfTool, self).__init__(*args, **kwargs)


class YumTool(tools_system_pm.YumTool):
    def __init__(self, *args, **kwargs):
        super(YumTool, self).__init__(*args, **kwargs)


class BrewTool(tools_system_pm.BrewTool):
    def __init__(self, *args, **kwargs):
        super(BrewTool, self).__init__(*args, **kwargs)


class PkgTool(tools_system_pm.PkgTool):
    def __init__(self, *args, **kwargs):
        super(PkgTool, self).__init__(*args, **kwargs)


class ChocolateyTool(tools_system_pm.ChocolateyTool):
    def __init__(self, *args, **kwargs):
        super(ChocolateyTool, self).__init__(*args, **kwargs)


class PkgUtilTool(tools_system_pm.PkgUtilTool):
    def __init__(self, *args, **kwargs):
        super(PkgUtilTool, self).__init__(*args, **kwargs)


class PacManTool(tools_system_pm.PacManTool):
    def __init__(self, *args, **kwargs):
        super(PacManTool, self).__init__(*args, **kwargs)


class ZypperTool(tools_system_pm.ZypperTool):
    def __init__(self, *args, **kwargs):
        super(ZypperTool, self).__init__(*args, **kwargs)


# Ready to use objects.
try:
    os_info = OSInfo()
except Exception as exc:
    logger.error(exc)
    ConanOutput().error("Error detecting os_info")
