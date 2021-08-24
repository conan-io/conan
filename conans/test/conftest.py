import os
import platform
import uuid

import pytest

from conans.client.tools import vswhere, which

tools_default_version = {
    'cmake': '3.15',
    'msys2': 'default',
    'cygwin': 'default',
    'mingw32': 'default',
    'mingw64': 'default',
    'ninja': '1.10.2',
    'bazel': 'default'
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
    },
    'ninja': {'Windows': {'1.10.2': 'C:/Tools/ninja/1.10.2'}},
    'bazel': {
        'Darwin': {'default': '/Users/jenkins/bin'},
        'Windows': {'default': 'C:/bazel/bin'},
    }
}

tools_environments = {
    'mingw32': {'Windows': {'MSYSTEM': 'MINGW32'}},
    'mingw64': {'Windows': {'MSYSTEM': 'MINGW64'}}
}


_cached_tools = {}


def _get_tool(name, version):
    cached = _cached_tools.setdefault(name, {}).get(version)
    if cached is None:
        tool_platform = platform.system()
        version = version or tools_default_version.get(name)
        tool_path = tool_env = None
        if version is not None:  # Must be found in locations
            try:
                tool_path = tools_locations[name][tool_platform][version]
            except KeyError:
                _cached_tools[name][version] = False
                return False
        try:
            tool_env = tools_environments[name][tool_platform]
        except KeyError:
            pass

        cached = tool_path, tool_env

        # Check this particular tool is installed
        if name == "visual_studio":
            if not vswhere():  # TODO: Missing version detection
                cached = False
        else:  # which based detection
            old_environ = None
            if tool_path is not None:
                old_environ = dict(os.environ)
                os.environ["PATH"] = tool_path + os.pathsep + os.environ["PATH"]
            if not which(name):  # TODO: This which doesn't detect version either
                cached = False
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
            if tool_name == "compiler":
                tool_name = {"Windows": "visual_studio",
                             "Linux": "gcc",
                             "Darwin": "clang"}.get(platform.system())
            tool_version = mark.kwargs.get('version')
            tool_found = _get_tool(tool_name, tool_version)
            if tool_found is False:
                version_msg = "Any" if tool_version is None else tool_version
                pytest.fail("Required '{}' tool version '{}' is not available".format(tool_name,
                                                                                      version_msg))

            tool_path, tool_env = tool_found
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
