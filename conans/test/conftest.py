import os
import platform

import pytest

from conans.client.tools import vswhere, which
from conans.errors import ConanException

tools_default_version = {
    'cmake': '3.15',
    'msys2': 'default',
    'cygwin': 'default',
    'mingw32': 'default',
    'mingw64': 'default'
}

tools_locations = {
    'msys2': {'Windows': {'default': os.getenv('CONAN_MSYS2_PATH', 'C:/msys64/usr/bin')}},
    'cygwin': {'Windows': {'default': os.getenv('CONAN_CYGWIN_PATH', 'C:/cygwin64/bin')}},
    'mingw32': {'Windows': {'default': os.getenv('CONAN_MINGW32_PATH', 'C:/msys64/mingw32/bin')}},
    'mingw64': {'Windows': {'default': os.getenv('CONAN_MINGW64_PATH', 'C:/msys64/mingw64/bin')}},
    'cmake': {
        'Windows': {
            '3.15': 'C:/cmake/cmake-3.15.7-win64-x64/bin',
            '3.16': 'C:/cmake/cmake-3.16.9-win64-x64/bin',
            '3.17': 'C:/cmake/cmake-3.17.5-win64-x64/bin',
            '3.19': 'C:/cmake/cmake-3.19.7-win64-x64/bin'
        },
        'Darwin': {
            '3.15': '/Users/jenkins/cmake/cmake-3.15.7/bin',
            '3.16': '/Users/jenkins/cmake/cmake-3.16.9/bin',
            '3.17': '/Users/jenkins/cmake/cmake-3.17.5/bin',
            '3.19': '/Users/jenkins/cmake/cmake-3.19.7/bin'
        },
        'Linux': {
            '3.15': '/usr/share/cmake-3.15.7/bin',
            '3.16': '/usr/share/cmake-3.16.9/bin',
            '3.17': '/usr/share/cmake-3.17.5/bin',
            '3.19': '/usr/share/cmake-3.19.7/bin'
        }
    }
}

tools_environments = {
    'mingw32': {'Windows': {'MSYSTEM': 'MINGW32'}},
    'mingw64': {'Windows': {'MSYSTEM': 'MINGW64'}}
}

tools_available = [
    'cmake',
    'gcc', 'clang', 'visual_studio', 'xcode',
    'msys2', 'cygwin', 'mingw32', 'mingw64',
    'autotools', 'pkg_config', 'premake', 'meson',
    'file',
    'git', 'svn',
    'compiler',
    'conan',  # Search the tool_conan test that needs conan itself
]

if not which("cmake"):
    tools_available.remove("cmake")

if not which("gcc"):
    tools_available.remove("gcc")
if not which("clang"):
    tools_available.remove("clang")
try:
    if not vswhere():
        tools_available.remove("visual_studio")
except ConanException:
    tools_available.remove("visual_studio")

if not any([x for x in ("gcc", "clang", "visual_studio") if x in tools_available]):
    tools_available.remove("compiler")

if not which("xcodebuild"):
    tools_available.remove("xcode")

if not which("file"):
    tools_available.remove("file")

if not which("git"):
    tools_available.remove("git")
if not which("svn"):
    tools_available.remove("svn")

if not which("autoconf") or not which("automake"):
    tools_available.remove("autotools")
if not which("meson"):
    tools_available.remove("meson")
if not which("pkg-config"):
    tools_available.remove("pkg_config")
if not which("premake"):
    tools_available.remove("premake")
if not which("conan"):
    tools_available.remove("conan")


def _get_tool_path(locations, name, version, tool_platform):
    path = None
    try:
        path = locations[name][tool_platform][version]
    except KeyError as exc:
        if version in str(exc):
            raise ConanException(exc)
    return path


def _get_tool_environment(environments, name, tool_platform):
    env = None
    try:
        env = environments[name][tool_platform]
    except KeyError:
        pass
    return env


@pytest.fixture(autouse=True)
def add_tool(request):
    tools_paths = []
    tools_env_vars = dict()
    for mark in request.node.iter_markers():
        if mark.name.startswith("tool_"):
            tool_name = mark.name[5:]
            version = mark.kwargs.get('version', None) or tools_default_version.get(tool_name)
            if version:
                try:
                    tool_path = _get_tool_path(tools_locations, tool_name, version, platform.system())
                    if tool_path:
                        tools_paths.append(tool_path)
                except ConanException:
                    pytest.fail("Required {} version: '{}' is not available".format(tool_name, version))

            tool_env = _get_tool_environment(tools_environments, tool_name, platform.system())
            if tool_env:
                tools_env_vars.update(tool_env)

    if tools_paths:
        tools_paths.append(os.environ["PATH"])
        temp_env = {'PATH': os.pathsep.join(tools_paths)}
        old_environ = dict(os.environ)
        os.environ.update(temp_env)
        os.environ.update(tools_env_vars)
        yield
        os.environ.clear()
        os.environ.update(old_environ)
    else:
        yield


def tool_check(mark):
    tool_name = mark.name[5:]
    if tool_name not in tools_available:
        pytest.fail("Required tool: '{}' is not available".format(tool_name))


def pytest_runtest_setup(item):
    # Every mark is a required tool, some specify a version
    for mark in item.iter_markers():
        if mark.name.startswith("tool_"):
            tool_check(mark)
