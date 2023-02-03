import pytest

from conan.tools.cmake import CMake
from conan.tools.cmake.presets import write_cmake_presets
from conans.client.conf import get_default_settings_yml
from conans.model.conf import Conf
from conans.model.settings import Settings
from conans.test.utils.mocks import ConanFileMock
from conans.test.utils.test_files import temp_folder


@pytest.mark.parametrize("cmake_path", [None, "cmake", "/opt/cmake-3.21/bin/cmake"])
def test_cmake_binary_path(cmake_path):
    """
    Testing that the proper CMake binary path is configured
    """
    settings = Settings.loads(get_default_settings_yml())
    settings.os = "Windows"
    settings.arch = "x86"
    settings.build_type = "Release"
    settings.compiler = "Visual Studio"
    settings.compiler.runtime = "MDd"
    settings.compiler.version = "14"

    conanfile = ConanFileMock()
    conf = Conf()
    if cmake_path:
        conf.define("tools.cmake:path", cmake_path)
    conanfile.conf = conf
    conanfile.folders.generators = "."
    conanfile.folders.set_base_generators(temp_folder())
    conanfile.settings = settings
    conanfile.folders.set_base_package(temp_folder())

    # Choose generator to match generic setttings
    write_cmake_presets(conanfile, "toolchain", "Visual Studio 14 2015", {})
    cmake = CMake(conanfile)
    cmake.configure()

    # When there is no configuration for CMake bin path, "cmake" is expected by default
    if not cmake_path:
        cmake_path = "cmake"

    assert conanfile.command.startswith(f"{cmake_path} -G")
