from contextlib import contextmanager

from conans.client.tools import win as tools_win

vs_installation_path = tools_win.vs_installation_path
vswhere = tools_win.vswhere
vs_comntools = tools_win.vs_comntools
find_windows_10_sdk = tools_win.find_windows_10_sdk
escape_windows_cmd = tools_win.escape_windows_cmd
get_cased_path = tools_win.get_cased_path
unix_path = tools_win.unix_path
run_in_windows_bash = tools_win.run_in_windows_bash
msvs_toolset = tools_win.msvs_toolset

MSYS2 = tools_win.MSYS2
MSYS = tools_win.MSYS
CYGWIN = tools_win.CYGWIN
WSL = tools_win.WSL
SFU = tools_win.SFU


@contextmanager
def vcvars(conanfile, *args, **kwargs):
    with tools_win.vcvars(output=conanfile.output, *args, **kwargs):
        yield


def msvc_build_command(conanfile, *args, **kwargs):
    return tools_win.msvc_build_command(output=conanfile.output, *args, **kwargs)


def build_sln_command(conanfile, *args, **kwargs):
    return tools_win.build_sln_command(output=conanfile.output, *args, **kwargs)


def vcvars_command(conanfile, *args, **kwargs):
    return tools_win.vcvars_command(output=conanfile.output, *args, **kwargs)


def vcvars_dict(conanfile, *args, **kwargs):
    return tools_win.vcvars_dict(output=conanfile.output, *args, **kwargs)


def latest_vs_version_installed(conanfile, *args, **kwargs):
    return tools_win.latest_vs_version_installed(output=conanfile.output, *args, **kwargs)
