import os
import pathlib
import platform
import textwrap
import uuid
from shutil import which

import pytest

from conans.client.conf.detect_vs import vswhere

"""
To override these locations with your own in your dev machine:
1. Create a conftest_user.py just besides this conftest.py file
2. This file is .gitignored, it will not be committed
3. Override the tools_locations, you can completely disabled some tools, tests will be skipped
4. Empty dicts, without specifying the path, means the tool is already in the system
   path


tools_locations = {
    'svn': {"disabled": True},
    'cmake': {
        "default": "3.19",
        "3.15": {},
        "3.16": {"disabled": True},
        "3.17": {"disabled": True},
        "3.19": {"path": {"Windows": "C:/ws/cmake/cmake-3.19.7-win64-x64/bin"}},
        # To explicitly skip one tool for one version, define the path as 'skip-tests'
        # if you don't define the path for one platform it will run the test with the
        # tool in the path. For example here it will skip the test with CMake in Darwin but
        # in Linux it will run with the version found in the path if it's not specified
        "3.23": {"path": {"Windows": "C:/ws/cmake/cmake-3.19.7-win64-x64/bin",
                          "Darwin": "skip-tests"}},
    },
    'ninja': {
        "1.10.2": {}
    },
    'meson': {"disabled": True},
    'bazel':  {
        "system": {"path": {'Windows': 'C:/ws/bazel/4.2.0'}},
    }
}
"""

MacOS_arm = all([platform.system() == "Darwin", platform.machine() == "arm64"])
homebrew_root = "/opt/homebrew" if MacOS_arm else "/usr/local"


tools_locations = {
    "clang": {"disabled": True},
    'visual_studio': {"default": "15",
                      "15": {},
                      "16": {"disabled": True},
                      "17": {"disabled": True}},
    'pkg_config': {
        "exe": "pkg-config",
        "default": "0.28",
        "0.28": {
            "path": {
                # Using chocolatey in Windows -> choco install pkgconfiglite --version 0.28
                'Windows': "C:/ProgramData/chocolatey/lib/pkgconfiglite/tools/pkg-config-lite-0.28-1/bin",
                'Darwin': f"{homebrew_root}/bin",
                'Linux': "/usr/bin"
            }
        }},
    'autotools': {"exe": "autoconf"},
    'cmake': {
        "default": "3.15",
        "3.15": {
            "path": {'Windows': 'C:/cmake/cmake-3.15.7-win64-x64/bin',
                     'Darwin': '/Users/jenkins/cmake/cmake-3.15.7/bin',
                     'Linux': '/usr/share/cmake-3.15.7/bin'}
        },
        "3.16": {
            "path": {'Windows': 'C:/cmake/cmake-3.16.9-win64-x64/bin',
                     'Darwin': '/Users/jenkins/cmake/cmake-3.16.9/bin',
                     'Linux': '/usr/share/cmake-3.16.9/bin'}
        },
        "3.17": {
            "path": {'Windows': 'C:/cmake/cmake-3.17.5-win64-x64/bin',
                     'Darwin': '/Users/jenkins/cmake/cmake-3.17.5/bin',
                     'Linux': '/usr/share/cmake-3.17.5/bin'}
        },
        "3.19": {
            "path": {'Windows': 'C:/cmake/cmake-3.19.7-win64-x64/bin',
                     'Darwin': '/Users/jenkins/cmake/cmake-3.19.7/bin',
                     'Linux': '/usr/share/cmake-3.19.7/bin'}
        },
        "3.23": {
            "path": {'Windows': 'C:/cmake/cmake-3.23.1-win64-x64/bin',
                     'Darwin': '/Users/jenkins/cmake/cmake-3.23.1/bin'
                               if not MacOS_arm else "skip-tests",
                     # Not available in Linux
                     'Linux': "skip-tests"}
        }
    },
    'ninja': {
        "default": "1.10.2",
        "1.10.2": {
            "path": {'Windows': 'C:/Tools/ninja/1.10.2'}
        }
    },
    # This is the non-msys2 mingw, which is 32 bits x86 arch
    'mingw': {
        "disabled": True,
        "platform": "Windows",
        "default": "system",
        "exe": "mingw32-make",
        "system": {"path": {'Windows': "C:/mingw"}},
    },
    'mingw32': {
        "platform": "Windows",
        "default": "system",
        "exe": "mingw32-make",
        "system": {"path": {'Windows': "C:/msys64/mingw32/bin"}},
    },
    'ucrt64': {
        "disabled": True,
        "platform": "Windows",
        "default": "system",
        "exe": "mingw32-make",
        "system": {"path": {'Windows': "C:/msys64/ucrt64/bin"}},
    },
    'mingw64': {
        "platform": "Windows",
        "default": "system",
        "exe": "mingw32-make",
        "system": {"path": {'Windows': "C:/msys64/mingw64/bin"}},
    },
    'msys2': {
        "platform": "Windows",
        "default": "system",
        "exe": "make",
        "system": {"path": {'Windows': "C:/msys64/usr/bin"}},
    },
    'msys2_clang64': {
        "disabled": True,
        "platform": "Windows",
        "default": "system",
        "exe": "clang",
        "system": {"path": {'Windows': "C:/msys64/clang64/bin"}},
    },
    'msys2_mingw64_clang64': {
        "disabled": True,
        "platform": "Windows",
        "default": "system",
        "exe": "clang",
        "system": {"path": {'Windows': "C:/msys64/mingw64/bin"}},
    },
    'cygwin': {
        "platform": "Windows",
        "default": "system",
        "exe": "make",
        "system": {"path": {'Windows': "C:/cygwin64/bin"}},
    },
    'bazel': {
        "default": "system",
        "system": {"path": {'Windows': 'C:/bazel/bin',
                            "Darwin": '/Users/jenkins/bin'}},
    },
    'premake': {
        "exe": "premake5",
        "default": "5.0.0",
        "5.0.0": {
            "path": {'Linux': '/usr/local/bin/premake5'}
        }
    },
    'xcodegen': {"platform": "Darwin"},
    'apt_get': {"exe": "apt-get"},
    'brew': {},
    'android_ndk': {
        "platform": "Darwin",
        "exe": "ndk-build",
    },
    # TODO: Intel oneAPI is not installed in CI yet. Uncomment this line whenever it's done.
    # "intel_oneapi": {
    #     "default": "2021.3",
    #     "exe": "dpcpp",
    #     "2021.3": {"path": {"Linux": "/opt/intel/oneapi/compiler/2021.3.0/linux/bin"}}
    # }
}


# TODO: Make this match the default tools (compilers) above automatically
arch = platform.machine()
arch_setting = "armv8" if arch in ["arm64", "aarch64"] else arch
default_profiles = {
    "Windows": textwrap.dedent("""\
        [settings]
        os=Windows
        arch=x86_64
        compiler=msvc
        compiler.version=191
        compiler.runtime=dynamic
        build_type=Release
        """),
    "Linux": textwrap.dedent(f"""\
        [settings]
        os=Linux
        arch={arch_setting}
        compiler=gcc
        compiler.version=8
        compiler.libcxx=libstdc++11
        build_type=Release
        """),
    "Darwin": textwrap.dedent(f"""\
        [settings]
        os=Macos
        arch={arch_setting}
        compiler=apple-clang
        compiler.version=13
        compiler.libcxx=libc++
        build_type=Release
        """)
}

try:
    from conans.test.conftest_user import tools_locations as user_tool_locations

    def update(d, u):
        for k, v in u.items():
            if isinstance(v, dict):
                d[k] = update(d.get(k, {}), v)
            else:
                d[k] = v
        return d

    update(tools_locations, user_tool_locations)
except ImportError as e:
    user_tool_locations = None


try:
    from conans.test.conftest_user import default_profiles as user_default_profiles
    default_profiles.update(user_default_profiles)
except ImportError as e:
    user_default_profiles = None

homebrew_root = "/opt/homebrew" if platform.machine() == "arm64" else "/usr/local"


tools_environments = {
    'mingw32': {'Windows': {'MSYSTEM': 'MINGW32'}},
    'mingw64': {'Windows': {'MSYSTEM': 'MINGW64'}},
    'ucrt64': {'Windows': {'MSYSTEM': 'UCRT64'}},
    'msys2_clang64': {"Windows": {"MSYSTEM": "CLANG64"}},
    'android_ndk': {'Darwin': {'TEST_CONAN_ANDROID_NDK': f'{homebrew_root}/share/android-ndk'}}
}


_cached_tools = {}


def _get_tool(name, version):
    # None: not cached yet
    # False = tool not available, legally skipped
    # True = tool not available, test error
    # (path, env) = tool available
    cached = _cached_tools.setdefault(name, {}).get(version)
    if cached is not None:
        return cached
    result = _get_individual_tool(name, version)
    _cached_tools[name][version] = result
    return result


def _get_individual_tool(name, version):
    tool = tools_locations.get(name, {})
    if tool.get("disabled"):
        return False

    tool_platform = platform.system()
    if tool.get("platform", tool_platform) != tool_platform:
        return None, None

    version = version or tool.get("default")
    tool_version = tool.get(version)
    if tool_version is not None:
        assert isinstance(tool_version, dict)
        if tool_version.get("disabled"):
            return False
        if name == "visual_studio":
            if vswhere():  # TODO: Missing version detection
                return None, None

        tool_path = tool_version.get("path", {}).get(tool_platform)
        tool_path = tool_path.replace("/", "\\") if tool_platform == "Windows" and tool_path is not None else tool_path
        # To allow to skip for a platform, we can put the path to None
        # "cmake": { "3.23": {
        #               "path": {'Windows': 'C:/cmake/cmake-3.23.1-win64-x64/bin',
        #                        'Darwin': '/Users/jenkins/cmake/cmake-3.23.1/bin',
        #                        'Linux': None}}
        #          }
        if tool_path == "skip-tests":
            return False
        elif tool_path is not None and not os.path.isdir(tool_path):
            return True
    else:
        if version is not None:  # if the version is specified, it should be in the conf
            return True
        tool_path = None

    try:
        tool_env = tools_environments[name][tool_platform]
    except KeyError:
        tool_env = None

    cached = tool_path, tool_env

    # Check this particular tool is installed
    old_environ = None
    if tool_path is not None:
        old_environ = dict(os.environ)
        os.environ["PATH"] = tool_path + os.pathsep + os.environ["PATH"]
    exe = tool.get("exe", name)
    exe_found = which(exe)  # TODO: This which doesn't detect version either
    exe_path = str(pathlib.Path(exe_found).parent) if exe_found else None
    if not exe_found:
        cached = True
        if tool_path is None:
            # will fail the test, not exe found and path None
            cached = True
    elif tool_path is not None and tool_path not in exe_found:
        # finds the exe in a path that is not the one set in the conf -> fail
        cached = True
    elif tool_path is None:
        cached = exe_path, tool_env

    if old_environ is not None:
        os.environ.clear()
        os.environ.update(old_environ)

    return cached


def pytest_configure(config):
    # register an additional marker
    config.addinivalue_line(
        "markers", "tool(name, version): mark test to require a tool by name"
    )


def pytest_runtest_teardown(item):
    if hasattr(item, "old_environ"):
        os.environ.clear()
        os.environ.update(item.old_environ)


def pytest_runtest_setup(item):
    tools_paths = []
    tools_env_vars = dict()
    for mark in item.iter_markers():
        if mark.name.startswith("tool_"):
            raise Exception("Invalid decorator @pytest.mark.{}".format(mark.name))

    kwargs = [mark.kwargs for mark in item.iter_markers(name="tool")]
    if any(kwargs):
        raise Exception("Invalid decorator @pytest.mark Do not use kwargs: {}".format(kwargs))
    tools_params = [mark.args for mark in item.iter_markers(name="tool")]
    for tool_params in tools_params:
        if len(tool_params) == 1:
            tool_name = tool_params[0]
            tool_version = None
        elif len(tool_params) == 2:
            tool_name, tool_version = tool_params
        else:
            raise Exception("Invalid arguments for mark.tool: {}".format(tool_params))

        result = _get_tool(tool_name, tool_version)
        if result is True:
            version_msg = "Any" if tool_version is None else tool_version
            pytest.fail("Required '{}' tool version '{}' is not available".format(tool_name,
                                                                                  version_msg))
        if result is False:
            version_msg = "Any" if tool_version is None else tool_version
            pytest.skip("Required '{}' tool version '{}' is not available".format(tool_name,
                                                                                  version_msg))

        tool_path, tool_env = result
        if tool_path:
            tools_paths.append(tool_path)
        if tool_env:
            tools_env_vars.update(tool_env)
        # Fix random failures CI because of this: https://issues.jenkins.io/browse/JENKINS-9104
        if tool_name == "visual_studio":
            tools_env_vars['_MSPDBSRV_ENDPOINT_'] = str(uuid.uuid4())

    if tools_paths or tools_env_vars:
        item.old_environ = dict(os.environ)
        tools_env_vars['PATH'] = os.pathsep.join(tools_paths + [os.environ["PATH"]])
        os.environ.update(tools_env_vars)
