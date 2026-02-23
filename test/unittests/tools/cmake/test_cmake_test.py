import pytest

from conan.internal.default_settings import default_settings_yml
from conan.tools.cmake import CMake
from conan.tools.cmake.presets import write_cmake_presets
from conan.internal.model.conf import Conf
from conan.internal.model.settings import Settings
from conan.test.utils.mocks import ConanFileMock
from conan.test.utils.test_files import temp_folder
from conan.tools.cmake.utils import cmake_escape_value


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
    settings = Settings.loads(default_settings_yml)
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
    settings = Settings.loads(default_settings_yml)

    conanfile = ConanFileMock()
    conanfile.conf = Conf()
    conanfile.folders.generators = "."
    conanfile.folders.set_base_generators(temp_folder())
    conanfile.settings = settings

    write_cmake_presets(conanfile, "toolchain", "Unix Makefiles", {})
    cmake = CMake(conanfile)
    cmake.configure(cli_args=["--graphviz=foo.dot"])
    assert "--graphviz=foo.dot" in conanfile.command


def test_run_ctest():
    settings = Settings.loads(default_settings_yml)
    settings.os = "Windows"
    settings.arch = "x86"
    settings.build_type = "Release"
    settings.compiler = "msvc"
    settings.compiler.runtime = "dynamic"
    settings.compiler.version = "193"

    conanfile = ConanFileMock()
    conanfile.conf = Conf()
    conanfile.conf.define("tools.cmake:ctest_args", ["--debug", "--output-junit myfile"])
    conanfile.conf.define("tools.build:verbosity", "verbose")

    conanfile.folders.generators = "."
    conanfile.folders.set_base_generators(temp_folder())
    conanfile.settings = settings

    write_cmake_presets(conanfile, "toolchain", "Ninja", {})
    cmake = CMake(conanfile)
    cmake.ctest(cli_args=["--schedule-random", "--quiet"])
    assert "--schedule-random --quiet --verbose --debug --output-junit myfile" in conanfile.command


@pytest.mark.parametrize("input_str, expected", [
    (r"PlainString", r"PlainString"),  # Case 1: Plain strings (No change)
    # Case 2: Individual characters (First-time escape)
    (r"C:\Path", r"C:\\Path"),
    (r'He said "Hi"', r'He said \"Hi\"'),
    (r"Cost is $10", r"Cost is \$10"),
    # Case 3: Complex mixed strings
    (r'Mixed \path and "quote" with $VAR', r'Mixed \\path and \"quote\" with \$VAR'),
    # Case 4: Partial escapes (Only unescaped parts get fixed)
    (r'\"Already" and \$Already$', r'\"Already\" and \$Already\$'),
    # Case 5: Edge cases
    (r'TrailingSlash\\', r'TrailingSlash\\'),
    (r"Double\\Slash", r"Double\\Slash"),
    (r"", r""),  # Empty string
])
def test_cmake_escape_correctness(input_str, expected):
    escaped = cmake_escape_value(input_str)
    assert escaped == expected
    assert cmake_escape_value(escaped) == expected
