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
from conans.client.tools.settings import *  # pylint: disable=unused-import
from conans.client.tools.apple import *
from conans.client.tools.android import *
# Tools form conans.util
from conans.util.env_reader import get_env
from conans.util.files import _generic_algorithm_sum, load, md5, md5sum, mkdir, relative_dirs, \
    rmdir, save as files_save, save_append, sha1sum, sha256sum, to_file_bytes, touch
from conans.util.log import logger
from conans.client.tools.version import Version
from conans.client.build.cppstd_flags import cppstd_flag_new as cppstd_flag  # pylint: disable=unused-import
from conans.client.build.cmake import CMake


class Tools(object):

    def __init__(self, output, requester, config):
        self.output = ConanOutput(sys.stdout, sys.stderr, True) if output is None else output
        self.requester = requester
        self.config = config
        # from conans.client.tools.files

        # INFO: It can be loaded dynamically e.g. dir(tools_files) ...

        self.chdir = tools_files.chdir
        self.human_size = tools_files.human_size
        self.untargz = tools_files.untargz
        self.check_with_algorithm_sum = tools_files.check_with_algorithm_sum
        self.check_sha1 = tools_files.check_sha1
        self.check_md5 = tools_files.check_md5
        self.check_sha256 = tools_files.check_sha256
        self.replace_prefix_in_pc_file = tools_files.replace_prefix_in_pc_file
        self.collect_libs = tools_files.collect_libs
        self.which = tools_files.which
        self.unix2dos = tools_files.unix2dos
        self.dos2unix = tools_files.dos2unix
        self.fix_symlinks = tools_files.fix_symlinks
        self.patch = tools_files.patch
        self.load = tools_files.load

        # from conans.client.tools.win
        self.vs_installation_path = tools_win.vs_installation_path
        self.vswhere = tools_win.vswhere
        self.vs_comntools = tools_win.vs_comntools
        self.find_windows_10_sdk = tools_win.find_windows_10_sdk
        self.escape_windows_cmd = tools_win.escape_windows_cmd
        self.get_cased_path = tools_win.get_cased_path
        self.unix_path = tools_win.unix_path
        self.run_in_windows_bash = tools_win.run_in_windows_bash
        self.msvs_toolset = tools_win.msvs_toolset

        # from conans.client.tools.oss
        self.args_to_string = tools_oss.args_to_string
        self.detected_architecture = tools_oss.detected_architecture
        self.detected_os = tools_oss.detected_os
        self.OSInfo = tools_oss.OSInfo
        self.os_info = self.OSInfo()
        self.cross_building = tools_oss.cross_building
        self.get_cross_building_settings = tools_oss.get_cross_building_settings
        self.get_gnu_triplet = tools_oss.get_gnu_triplet

        self.CMake = CMake

# This global variables are intended to store the configuration of the running Conan application
#_global_output = None
#_global_requester = None
#_global_config = None


#def set_global_instances(the_output, the_requester, config):
#    global _global_output
#    global _global_requester
#    global _global_config

    # TODO: pass here the configuration file, and make the work here (explicit!)
#    _global_output = the_output
#    _global_requester = the_requester
#    _global_config = config


#def get_global_instances():
#    return _global_output, _global_requester

# Assign a default, will be overwritten in the factory of the ConanAPI
#set_global_instances(the_output=ConanOutput(sys.stdout, sys.stderr, True), the_requester=requests,
#                     config=None)


    """
    From here onwards only currification is expected, no logic
    """


    def save(self, path, content, append=False):
        # TODO: All this three functions: save, save_append and this one should be merged into one.
        if append:
            save_append(path=path, content=content)
        else:
            files_save(path=path, content=content, only_if_modified=False)


    # From conans.client.tools.net
    ftp_download = tools_net.ftp_download


    def download(self, *args, **kwargs):
        return tools_net.download(out=self.output, requester=self.requester, config=self.config, *args, **kwargs)


    def get(self, *args, **kwargs):
        return tools_net.get(output=self.output, requester=self.requester, *args, **kwargs)

    def unzip(self, *args, **kwargs):
        return tools_files.unzip(output=self.output, *args, **kwargs)


    def replace_in_file(self, *args, **kwargs):
        return tools_files.replace_in_file(output=self.output, *args, **kwargs)


    def replace_path_in_file(self, *args, **kwargs):
        return tools_files.replace_path_in_file(output=self.output, *args, **kwargs)

    def cpu_count(self, *args, **kwargs):
        return tools_oss.cpu_count(output=self.output, *args, **kwargs)

    @contextmanager
    def vcvars(self, *args, **kwargs):
        with tools_win.vcvars(output=self.output, *args, **kwargs):
            yield

    def msvc_build_command(self, *args, **kwargs):
        return tools_win.msvc_build_command(output=self.output, *args, **kwargs)


    def build_sln_command(self, *args, **kwargs):
        return tools_win.build_sln_command(output=self.output, *args, **kwargs)

    def vcvars_command(self, *args, **kwargs):
        return tools_win.vcvars_command(output=self.output, *args, **kwargs)

    def vcvars_dict(self, *args, **kwargs):
        return tools_win.vcvars_dict(output=self.output, *args, **kwargs)

    def latest_vs_version_installed(self, *args, **kwargs):
        return tools_win.latest_vs_version_installed(output=self.output, *args, **kwargs)

    class SystemPackageTool(tools_system_pm.SystemPackageTool):

        def __init__(self, *args, **kwargs):
            super(Tools.SystemPackageTool, self).__init__(output=self.output, *args, **kwargs)

    class NullTool(tools_system_pm.NullTool):
        def __init__(self, *args, **kwargs):
            super(Tools.NullTool, self).__init__(output=self.output, *args, **kwargs)

    class AptTool(tools_system_pm.AptTool):
        def __init__(self, *args, **kwargs):
            super(Tools.AptTool, self).__init__(output=self.output, *args, **kwargs)

    class DnfTool(tools_system_pm.DnfTool):
        def __init__(self, *args, **kwargs):
            super(Tools.DnfTool, self).__init__(output=self.output, *args, **kwargs)

    class YumTool(tools_system_pm.YumTool):
        def __init__(self, *args, **kwargs):
            super(Tools.YumTool, self).__init__(output=self.output, *args, **kwargs)

    class BrewTool(tools_system_pm.BrewTool):
        def __init__(self, *args, **kwargs):
            super(Tools.BrewTool, self).__init__(output=self.output, *args, **kwargs)

    class PkgTool(tools_system_pm.PkgTool):
        def __init__(self, *args, **kwargs):
            super(Tools.PkgTool, self).__init__(output=self.output, *args, **kwargs)

    class ChocolateyTool(tools_system_pm.ChocolateyTool):
        def __init__(self, *args, **kwargs):
            super(Tools.ChocolateyTool, self).__init__(output=self.output, *args, **kwargs)

    class PkgUtilTool(tools_system_pm.PkgUtilTool):
        def __init__(self, *args, **kwargs):
            super(Tools.PkgUtilTool, self).__init__(output=self.output, *args, **kwargs)

    class PacManTool(tools_system_pm.PacManTool):
        def __init__(self, *args, **kwargs):
            super(Tools.PacManTool, self).__init__(output=self.output, *args, **kwargs)

    class ZypperTool(tools_system_pm.ZypperTool):
        def __init__(self, *args, **kwargs):
            super(Tools.ZypperTool, self).__init__(output=self.output, *args, **kwargs)



MSYS2 = tools_win.MSYS2
MSYS = tools_win.MSYS
CYGWIN = tools_win.CYGWIN
WSL = tools_win.WSL
SFU = tools_win.SFU

# Ready to use objects.
try:
    os_info = tools_oss.OSInfo()
except Exception as exc:
    logger.error(exc)
    # no global access for output, fragile
    output = ConanOutput(sys.stdout, sys.stderr, True)
    output.error("Error detecting os_info")
