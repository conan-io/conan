import pytest

from conan.tools.cmake import CMake
from conan.tools.cmake.presets import write_cmake_presets
from conans.client.conf import get_default_settings_yml
from conans.model.conf import Conf
from conans.model.settings import Settings
from conan.test.utils.mocks import ConanFileMock
from conan.test.utils.test_files import temp_folder


@pytest.mark.parametrize("generator,target", [
    ("NMake Makefiles", "test"),
    ("Ninja Makefiles", "test"),
    ("Ninja Multi-Config", "test"),
    ("Unix Makefiles", "test"),
    ("Visual Studio 14 2015", "RUN_TESTS"),
    ("Xcode", "RUN_TESTS"),
])
def test_run_tests(generator, target):
    """
    Testing that the proper test target is picked for different generators, especially
    multi-config ones.
    Issue related: https://github.com/conan-io/conan/issues/11405
    """
    settings = Settings.loads(get_default_settings_yml())
    settings.os = "Windows"
    settings.arch = "x86"
    settings.build_type = "Release"
    settings.compiler = "msvc"
    settings.compiler.runtime = "dynamic"
    settings.compiler.version = "193"

    conanfile = ConanFileMock()
    conanfile.conf = Conf()
    conanfile.folders.generators = "."
    conanfile.folders.set_base_generators(temp_folder())
    conanfile.settings = settings

    write_cmake_presets(conanfile, "toolchain", generator, {})
    cmake = CMake(conanfile)
    cmake.test()

    search_pattern = "--target {}"
    assert search_pattern.format(target) in conanfile.command


def test_cli_args_configure():
    settings = Settings.loads(get_default_settings_yml())

    conanfile = ConanFileMock()
    conanfile.conf = Conf()
    conanfile.folders.generators = "."
    conanfile.folders.set_base_generators(temp_folder())
    conanfile.settings = settings

    write_cmake_presets(conanfile, "toolchain", "Unix Makefiles", {})
    cmake = CMake(conanfile)
    cmake.configure(cli_args=["--graphviz=foo.dot"])
    assert "--graphviz=foo.dot" in conanfile.command
