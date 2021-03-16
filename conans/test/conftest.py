import os
import platform

import pytest

from conans.client.tools import vswhere, which
from conans.errors import ConanException

tool_locations = {
    'msys2': {'Windows': {'default': os.getenv("CONAN_MSYS2_PATH", "C:/msys64/usr/bin")}},
    'cygwin': {'Windows': {'default': os.getenv("CONAN_CYGWIN_PATH", "C:/cygwin64/bin")}},
    'mingw32': {'Windows': {'default': os.getenv('CONAN_MINGW32_PATH', "C:/msys64/mingw32/bin")}},
    'mingw64': {'Windows': {'default': os.getenv('CONAN_MINGW64_PATH', "C:/msys64/mingw64/bin")}},
    'cmake': {
        'Windows': {
            'default': 'C:/Program Files/Cmake/bin',
            '3.16': 'C:/cmake/cmake-3.16.9-win64-x64/bin'
        }
    }
}

tool_environments = {
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


@pytest.fixture(autouse=True)
def add_tool(request):
    add_tools = []
    env_tools = dict()
    for mark in request.node.iter_markers():
        if mark.name.startswith("tool_"):
            version = mark.kwargs.get('version', 'default')
            tool_name = mark.name[5:]
            if tool_name in tool_locations and tool_locations[tool_name].get(platform.system()):
                tool_versions = tool_locations[tool_name].get(platform.system())
                if version in tool_versions:
                    add_tools.append(tool_versions[version])
                else:
                    pytest.fail("Required {} version: '{}' is not available".format(tool_name,
                                                                                    version))

            if tool_name in tool_environments and tool_environments[tool_name].get(platform.system()):
                tool_env = tool_environments[tool_name].get(platform.system())
                env_tools.update(tool_env)

    if add_tools:
        add_tools.append(os.environ["PATH"])
        temp_env = {'PATH': os.pathsep.join(add_tools)}
        old_environ = dict(os.environ)
        os.environ.update(temp_env)
        os.environ.update(env_tools)
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
