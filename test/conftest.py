import os
import pathlib
import platform
import re
import shutil
import tempfile
import uuid
from shutil import which

import pytest
import requests

from conans.client.conf.detect_vs import vswhere
from conans.model.version import Version
from conan.tools.files import unzip

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
        "3.15": {"download": True},
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

# Location for automatically downloaded tools
tools_root = os.path.join(os.path.dirname(__file__), "tools")

tools_locations = {
    "clang": {"disabled": True},
    'visual_studio': {"default": "15",
                      "15": {},
                      "16": {"disabled": True},
                      "17": {}},
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
        "3.15": {"download": True},
        "3.16": {"download": True},
        "3.17": {"download": True},
        "3.19": {"download": True},
        "3.23": {"download": True},
        "3.28": {"download": True},
    },
    'ninja': {
        "default": "1.10.2",
        "1.10.2": {}  # Installed via pip
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
        "default": "6.3.2",
        "6.3.2": {"download": True},
        "7.1.2": {"download": True},
    },
    'premake': {
        "exe": "premake5",
        "default": "5.0.0-beta2",
        "5.0.0-beta2": {"download": True}
    },
    'xcodegen': {"platform": "Darwin"},
    'apt_get': {"exe": "apt-get"},
    'brew': {},
    'android_ndk': {
        "platform": "Darwin",
        "exe": "ndk-build",
        "default": "system",
        "system": {
            "path": {'Darwin': f'{homebrew_root}/share/android-ndk'}
        }
    },
    "qbs": {
        "disabled": True,
        "default": "1.24.1",
        "1.24.1": {"download": True},
    },
    # TODO: Intel oneAPI is not installed in CI yet. Uncomment this line whenever it's done.
    # "intel_oneapi": {
    #     "default": "2021.3",
    #     "exe": "dpcpp",
    #     "2021.3": {"path": {"Linux": "/opt/intel/oneapi/compiler/2021.3.0/linux/bin"}}
    # }
}


# TODO: Make this match the default tools (compilers) above automatically


try:
    from test.conftest_user import tools_locations as user_tool_locations

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
    'mingw64': {'Windows': {'MSYSTEM': 'MINGW64'}},
    'ucrt64': {'Windows': {'MSYSTEM': 'UCRT64'}},
    'msys2_clang64': {"Windows": {"MSYSTEM": "CLANG64"}}
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
        if tool_version.get("download"):
            tool_path = _download_tool(name, version)
        else:
            tool_path = tool_version.get("path", {}).get(tool_platform)
            tool_path = tool_path.replace("/", "\\") if tool_platform == "Windows" and tool_path is not None else tool_path
        # To allow to skip for a platform, we can put the path to "skip-tests"
        # "cmake": { "3.23": {
        #               "path": {'Windows': 'C:/cmake/cmake-3.23.1-win64-x64/bin',
        #                        'Darwin': '/Users/jenkins/cmake/cmake-3.23.1/bin',
        #                        'Linux': "skip-tests"}}
        #          }
        if tool_path == "skip-tests":
            return False
        elif tool_path is not None and not os.path.isdir(tool_path):
            return True
    elif version is not None:  # if the version is specified, it should be in the conf
        return True
    else:
        tool_path = None

    tool_env = tools_environments.get(name, {}).get(tool_platform)
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


def _download_tool(name, version):
    if name == "bazel":
        return _download_bazel(version)
    elif name == "cmake":
        return _download_cmake(version)
    elif name == "premake":
        return _download_premake(version)
    elif name == "qbs":
        return _download_qbs(version)
    raise Exception(f"Automatic downloads are not supported for '{name}'")

def _download_and_extract(url, output_dir):
    r = requests.get(url, allow_redirects=True)
    r.raise_for_status()
    suffix = ".zip" if url.endswith(".zip") else ".tar.gz"
    with tempfile.NamedTemporaryFile(suffix=suffix) as f:
        f.write(r.content)
        unzip(None, f.name, output_dir, strip_root=True)

def _get_bazel_download_url(version):
    file_os = platform.system().lower()
    if file_os not in ["windows", "darwin", "linux"]:
        raise Exception(f"Bazel is not available for {platform.system()}")
    if platform.machine() in ["x86_64", "AMD64"]:
        file_arch = "x86_64"
    elif platform.machine().lower() in ["aarch64", "arm64"]:
        file_arch = "aarch64"
    else:
        raise Exception(f"Bazel is not available for {platform.system()} {platform.machine()}")
    file = f"bazel-{version}-{file_os}-{file_arch}"
    if file_os == "windows":
        file += ".exe"
    return f"https://github.com/bazelbuild/bazel/releases/download/{version}/{file}"

def _download_bazel(version):
    """
    Download Bazel to test/tools/bazel/<version> and return the path to the binary directory.
    """
    output_dir = os.path.join(tools_root, "bazel", version)
    if os.path.exists(output_dir):
        return output_dir
    url = _get_bazel_download_url(version)
    os.makedirs(output_dir, exist_ok=True)
    r = requests.get(url, allow_redirects=True)
    r.raise_for_status()
    filename = "bazel.exe" if platform.system() == "Windows" else "bazel"
    path = os.path.join(output_dir, filename)
    with open(path, "wb") as f:
        f.write(r.content)
    if platform.system() != "Windows":
        os.chmod(path, os.stat(path).st_mode | 0o111)
    return output_dir

def _get_cmake_download_url(version):
    assert isinstance(version, str)
    assert re.fullmatch(r"\d+\.\d+", version)
    # Latest versions as of 2024-06
    full_version = {
        "3.15": "3.15.7",
        "3.16": "3.16.9",
        "3.17": "3.17.5",
        "3.19": "3.19.8",
        "3.23": "3.23.5",
        "3.28": "3.28.6",
    }[version]
    version = Version(version)
    file_os = None
    file_arch = None
    archive_format = "tar.gz"
    if platform.system() == "Windows":
        file_os = "win64" if version >= "3.19" else "windows"
        archive_format = "zip"
        if platform.machine() == "AMD64":
            file_arch = "x64" if version >= "3.20" else "x64_x64"
        elif platform.machine() == "ARM64" and version >= "3.24":
            file_arch = "arm64"
    elif platform.system() == "Darwin":
        if version >= "3.19":
            file_os = "macos"
            file_arch = "universal"
        elif platform.machine() == "x86_64":
            file_os = "Darwin"
            file_arch = "x86_64"
    elif platform.system() == "Linux":
        file_os = "linux" if version >= "3.20" else "Linux"
        if platform.machine() in ["x86_64", "AMD64"]:
            file_arch = "x86_64"
        elif platform.machine().lower() in ["aarch64", "arm64"] and version >= "3.19":
            file_arch = "aarch64"
    if not file_os or not file_arch:
        raise Exception(
            f"CMake v{full_version} is not available for {platform.system()} {platform.machine()}"
        )
    file = f"cmake-{full_version}-{file_os}-{file_arch}.{archive_format}"
    url = f"https://github.com/Kitware/CMake/releases/download/v{full_version}/{file}"
    return url


def _download_cmake(version):
    """
    Download CMake to test/tools/cmake/<version> and return the path to the binary directory.
    """
    output_dir = os.path.join(tools_root, "cmake", version)
    if os.path.exists(output_dir):
        return os.path.join(output_dir, "bin")
    url = _get_cmake_download_url(version)
    _download_and_extract(url, output_dir)
    # Save some space
    shutil.rmtree(os.path.join(output_dir, "doc"))
    shutil.rmtree(os.path.join(output_dir, "man"))
    return os.path.join(output_dir, "bin")

def _get_premake_download_url(version):
    if platform.system() == "Darwin":
        file = f"premake-{version}-macosx.tar.gz"
    elif platform.system() == "Linux" and platform.machine() == "x86_64":
        file = f"premake-{version}-linux.tar.gz"
    elif platform.system() == "Windows" and platform.machine() == "AMD64":
        file = f"premake-{version}-windows.zip"
    else:
        raise Exception(
            f"Premake v{version} is not available for {platform.system()} {platform.machine()}"
        )
    return f"https://github.com/premake/premake-core/releases/download/v{version}/{file}"

def _download_premake(version):
    """
    Download Premake to test/tools/premake/<version> and return the path to the binary directory.
    """
    output_dir = os.path.join(tools_root, "premake", version)
    if os.path.exists(output_dir):
        return output_dir
    url = _get_premake_download_url(version)
    _download_and_extract(url, output_dir)
    return output_dir

def _get_qbs_download_url(version):
    if platform.system() == "Linux" and platform.machine() == "x86_64":
        file = f"qbs-linux-x86_64-{version}.tar.gz"
    elif platform.system() == "Windows" and platform.machine() == "AMD64":
        file = f"qbs-windows-x86_64-{version}.zip"
    elif platform.system() == "Darwin":
        raise Exception(f"Qbs v{version} must be installed via MacPorts or Homebrew on macOS")
    else:
        raise Exception(
            f"Qbs v{version} is not available for {platform.system()} {platform.machine()}"
        )
    return f"https://download.qt.io/official_releases/qbs/{version}/{file}"


def _download_qbs(version):
    """
    Download CMake to test/tools/qbs/<version> and return the path to the binary directory.
    """
    output_dir = os.path.join(tools_root, "qbs", version)
    if os.path.exists(output_dir):
        return os.path.join(output_dir, "bin")
    url = _get_qbs_download_url(version)
    _download_and_extract(url, output_dir)
    return os.path.join(output_dir, "bin")
