import pytest
from conans.errors import ConanException

from conans.client.tools import vswhere, which

tools_available = [
    'cmake',
    'gcc', 'clang', 'visual_studio',
    'autotools', 'pkg_config', 'premake',
    'file',
    'git', 'svn',
]

if not which("cmake"):
    tools_available.remove("cmake")

if not which("gcc"):
    tools_available.remove("gcc")
if not which("clang"):
    tools_available.remove("clang")

try:
    vswhere()
except ConanException:
    tools_available.remove("visual_studio")

if not which("file"):
    tools_available.remove("file")

if not which("git"):
    tools_available.remove("git")
if not which("svn"):
    tools_available.remove("svn")

if not which("autoconf") or not which("automake"):
    tools_available.remove("autotools")
if not which("pkg-config"):
    tools_available.remove("pkg-config")
if not which("premake"):
    tools_available.remove("premake")


def tool_check(mark):
    tool_name = mark.name[5:]
    if tool_name not in tools_available:
        pytest.skip("required {} not satisfied".format(tool_name))


def pytest_runtest_setup(item):
    # Every mark is a required tool, some specify a version
    for mark in item.iter_markers():
        if mark.name.startswith("tool_"):
            return tool_check(mark)
