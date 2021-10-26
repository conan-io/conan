import os
import platform
import uuid

import pytest

from conans.client.tools import vswhere, which

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
                'Windows': "C:/ProgramData/chocolatey/lib/pkgconfiglite/tools/pkg-config-lite-0.28-1/bin"
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
        }
    },
    'ninja': {
        "default": "1.10.2",
        "1.10.2": {
            "path": {'Windows': 'C:/Tools/ninja/1.10.2'}
        }
    },
    'mingw32': {
        "platform": "Windows",
        "default": "system",
        "exe": "mingw32-make",
        "system": {"path": {'Windows': "C:/msys64/mingw32/bin"}},
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
    'cygwin': {
        "platform": "Windows",
        "default": "system",
        "exe": "make",
        "system": {"path": {'Windows': "C:/cygwin64/bin"}},
    },
    'bazel':  {
        "default": "system",
        "system": {"path": {'Windows': 'C:/bazel/bin',
                            "Darwin": '/Users/jenkins/bin'}},
    },
    # TODO: Intel oneAPI is not installed in CI yet. Uncomment this line whenever it's done.
    # "intel_oneapi": {
    #     "default": "2021.3",
    #     "exe": "dpcpp",
    #     "2021.3": {"path": {"Linux": "/opt/intel/oneapi/compiler/2021.3.0/linux/bin"}}
    # }
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

tools_environments = {
    'mingw32': {'Windows': {'MSYSTEM': 'MINGW32'}},
    'mingw64': {'Windows': {'MSYSTEM': 'MINGW64'}}
}


_cached_tools = {}


def _get_tool(name, version):
    # None: not cached yet
    # False = tool not available, legally skipped
    # True = tool not available, test error
    # (path, env) = tool available
    cached = _cached_tools.setdefault(name, {}).get(version)
    if cached is None:
        tool = tools_locations.get(name, {})
        if tool.get("disabled"):
            _cached_tools[name][version] = False
            return False

        tool_platform = platform.system()
        if tool.get("platform", tool_platform) != tool_platform:
            _cached_tools[name][version] = None, None
            return None, None

        exe = tool.get("exe", name)
        version = version or tool.get("default")
        tool_version = tool.get(version)
        if tool_version is not None:
            assert isinstance(tool_version, dict)
            if tool_version.get("disabled"):
                _cached_tools[name][version] = False
                return False
            tool_path = tool_version.get("path", {}).get(tool_platform)
        else:
            if version is not None:  # if the version is specified, it should be in the conf
                _cached_tools[name][version] = True
                return True
            tool_path = None

        try:
            tool_env = tools_environments[name][tool_platform]
        except KeyError:
            tool_env = None

        cached = tool_path, tool_env

        # Check this particular tool is installed
        if name == "visual_studio":
            if not vswhere():  # TODO: Missing version detection
                cached = True
        else:  # which based detection
            old_environ = None
            if tool_path is not None:
                old_environ = dict(os.environ)
                os.environ["PATH"] = tool_path + os.pathsep + os.environ["PATH"]
            if not which(exe):  # TODO: This which doesn't detect version either
                cached = True
            if old_environ is not None:
                os.environ.clear()
                os.environ.update(old_environ)

        _cached_tools[name][version] = cached

    return cached


@pytest.fixture(autouse=True)
def add_tool(request):
    tools_paths = []
    tools_env_vars = dict()
    for mark in request.node.iter_markers():
        if mark.name.startswith("tool_"):
            tool_name = mark.name[5:]
            tool_version = mark.kwargs.get('version')
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
        old_environ = dict(os.environ)
        tools_env_vars['PATH'] = os.pathsep.join(tools_paths + [os.environ["PATH"]])
        os.environ.update(tools_env_vars)
        yield
        os.environ.clear()
        os.environ.update(old_environ)
    else:
        yield
