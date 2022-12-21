import platform
import pytest

from conan.tools.cmake import CMake
from conan.tools.cmake.presets import write_cmake_presets
from conans.client.conf import get_default_settings_yml
from conans.model.conf import Conf
from conans.model.settings import Settings
from conans.test.utils.mocks import ConanFileMock
from conans.test.utils.test_files import temp_folder


@pytest.mark.parametrize("generator", [
    ("NMake Makefiles"),
    ("Ninja Makefiles"),
    ("Ninja Multi-Config"),
    ("Unix Makefiles"),
    ("Visual Studio 14 2015"),
    ("Xcode"),
])
def test_run_install_component(generator):
    """
    Testing that the proper component is installed.
    Issue related: https://github.com/conan-io/conan/issues/10359
    """
    settings = Settings.loads(get_default_settings_yml())
    settings.os = "Windows"
    settings.arch = "x86"
    settings.build_type = "Release"
    settings.compiler = "Visual Studio"
    settings.compiler.runtime = "MDd"
    settings.compiler.version = "14"

    conanfile = ConanFileMock()
    conanfile.conf = Conf()
    conanfile.folders.generators = "."
    conanfile.folders.set_base_generators(temp_folder())
    conanfile.settings = settings
    conanfile.folders.set_base_package(temp_folder())

    write_cmake_presets(conanfile, "toolchain", generator, {})
    cmake = CMake(conanfile)
    cmake.install(component="foo")

    assert "--component foo" in conanfile.command


@pytest.mark.parametrize("generator", [
    ("NMake Makefiles"),
    ("Ninja Makefiles"),
    ("Ninja Multi-Config"),
    ("Unix Makefiles"),
    ("Visual Studio 14 2015"),
    ("Xcode"),
])
def test_run_install_no_component(generator):
    settings = Settings.loads(get_default_settings_yml())
    settings.os = "Windows"
    settings.arch = "x86"
    settings.build_type = "Release"
    settings.compiler = "Visual Studio"
    settings.compiler.runtime = "MDd"
    settings.compiler.version = "14"

    conanfile = ConanFileMock()
    conanfile.conf = Conf()
    conanfile.folders.generators = "."
    conanfile.folders.set_base_generators(temp_folder())
    conanfile.settings = settings
    conanfile.folders.set_base_package(temp_folder())

    write_cmake_presets(conanfile, "toolchain", generator, {})
    cmake = CMake(conanfile)
    cmake.install()

    assert "--component" not in conanfile.command