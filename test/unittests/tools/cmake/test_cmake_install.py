from conan.tools.cmake import CMake
from conan.tools.cmake.presets import write_cmake_presets
from conans.client.conf import get_default_settings_yml
from conans.model.conf import Conf
from conans.model.settings import Settings
from conan.test.utils.mocks import ConanFileMock
from conan.test.utils.test_files import temp_folder


def test_run_install_component():
    """
    Testing that the proper component is installed.
    Issue related: https://github.com/conan-io/conan/issues/10359
    """
    # Load some generic windows settings
    settings = Settings.loads(get_default_settings_yml())
    settings.os = "Windows"
    settings.arch = "x86"
    settings.build_type = "Release"
    settings.compiler = "msvc"
    settings.compiler.runtime = "dynamic"
    settings.compiler.version = "190"

    conanfile = ConanFileMock()
    conanfile.conf = Conf()
    conanfile.folders.generators = "."
    conanfile.folders.set_base_generators(temp_folder())
    conanfile.settings = settings
    conanfile.folders.set_base_package(temp_folder())

    # Choose generator to match generic settings
    write_cmake_presets(conanfile, "toolchain", "Visual Studio 14 2015", {})
    cmake = CMake(conanfile)
    cmake.install(component="foo")

    assert "--component foo" in conanfile.command


def test_run_install_strip():
    """
    Testing that the install/strip rule is called
    Issue related: https://github.com/conan-io/conan/issues/14166
    """

    settings = Settings.loads(get_default_settings_yml())
    settings.os = "Linux"
    settings.arch = "x86_64"
    settings.build_type = "Release"
    settings.compiler = "gcc"
    settings.compiler.version = "11"

    conanfile = ConanFileMock()

    conanfile.conf = Conf()
    conanfile.conf.define("tools.cmake:install_strip", True)

    conanfile.folders.generators = "."
    conanfile.folders.set_base_generators(temp_folder())
    conanfile.settings = settings
    conanfile.folders.set_base_package(temp_folder())

    write_cmake_presets(conanfile, "toolchain", "Unix Makefiles", {})
    cmake = CMake(conanfile)
    cmake.install()
    assert "--strip" in conanfile.command


def test_run_install_cli_args():
    """
    Testing that the passing cli_args to install works
    Issue related: https://github.com/conan-io/conan/issues/14235
    """

    settings = Settings.loads(get_default_settings_yml())
    settings.os = "Linux"
    settings.arch = "x86_64"
    settings.build_type = "Release"
    settings.compiler = "gcc"
    settings.compiler.version = "11"

    conanfile = ConanFileMock()

    conanfile.conf = Conf()

    conanfile.folders.generators = "."
    conanfile.folders.set_base_generators(temp_folder())
    conanfile.settings = settings
    conanfile.folders.set_base_package(temp_folder())

    write_cmake_presets(conanfile, "toolchain", "Unix Makefiles", {})
    cmake = CMake(conanfile)
    cmake.install(cli_args=["--prefix=/tmp"])
    assert "--prefix=/tmp" in conanfile.command


def test_run_install_cli_args_strip():
    """
    Testing that the install/strip rule is called when using cli_args
    Issue related: https://github.com/conan-io/conan/issues/14235
    """

    settings = Settings.loads(get_default_settings_yml())
    settings.os = "Linux"
    settings.arch = "x86_64"
    settings.build_type = "Release"
    settings.compiler = "gcc"
    settings.compiler.version = "11"

    conanfile = ConanFileMock()

    conanfile.conf = Conf()

    conanfile.folders.generators = "."
    conanfile.folders.set_base_generators(temp_folder())
    conanfile.settings = settings
    conanfile.folders.set_base_package(temp_folder())

    write_cmake_presets(conanfile, "toolchain", "Unix Makefiles", {})
    cmake = CMake(conanfile)
    cmake.install(cli_args=["--strip"])
    assert "--strip" in conanfile.command
