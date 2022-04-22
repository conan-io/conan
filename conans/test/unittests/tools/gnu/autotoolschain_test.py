import pytest

from conan.tools.gnu import AutotoolsToolchain
from conans.errors import ConanException
from conans.test.utils.mocks import ConanFileMock, MockSettings


def test_get_gnu_triplet_for_cross_building():
    """
    Testing AutotoolsToolchain and _get_gnu_triplet() function in case of
    having os=Windows and cross compiling
    """
    # Issue: https://github.com/conan-io/conan/issues/10139
    settings = MockSettings({"build_type": "Release",
                             "compiler": "gcc",
                             "compiler.version": "10.2",
                             "os": "Windows",
                             "arch": "x86_64"})
    conanfile = ConanFileMock()
    conanfile.settings = settings
    conanfile.settings_build = MockSettings({"os": "Solaris", "arch": "x86"})
    autotoolschain = AutotoolsToolchain(conanfile)
    assert autotoolschain._host == "x86_64-w64-mingw32"
    assert autotoolschain._build == "i686-solaris"


@pytest.mark.parametrize("runtime, runtime_type, expected",
                         [("static", "Debug", "MTd"),
                          ("static", "Release", "MT"),
                          ("dynamic", "Debug", "MDd"),
                          ("dynamic", "Release", "MD")])
def test_msvc_runtime(runtime, runtime_type, expected):
    """
    Testing AutotoolsToolchain with the msvc compiler adjust the runtime
    """
    # Issue: https://github.com/conan-io/conan/issues/10139
    settings = MockSettings({"build_type": "Release",
                             "compiler": "msvc",
                             "compiler.runtime": runtime,
                             "compiler.runtime_type": runtime_type,
                             "os": "Windows",
                             "arch": "x86_64"})
    conanfile = ConanFileMock()
    conanfile.settings = settings
    conanfile.settings_build = settings
    autotoolschain = AutotoolsToolchain(conanfile)
    expected_flag = "-{}".format(expected)
    assert autotoolschain.msvc_runtime_flag == expected_flag
    env = autotoolschain.environment().vars(conanfile)
    assert expected_flag in env["CFLAGS"]
    assert expected_flag in env["CXXFLAGS"]


@pytest.mark.parametrize("runtime", ["MTd", "MT", "MDd", "MD"])
def test_visual_runtime(runtime):
    """
    Testing AutotoolsToolchain with the msvc compiler adjust the runtime
    """
    # Issue: https://github.com/conan-io/conan/issues/10139
    settings = MockSettings({"build_type": "Release",
                             "compiler": "Visual Studio",
                             "compiler.runtime": runtime,
                             "os": "Windows",
                             "arch": "x86_64"})
    conanfile = ConanFileMock()
    conanfile.settings = settings
    conanfile.settings_build = settings
    autotoolschain = AutotoolsToolchain(conanfile)
    expected_flag = "-{}".format(runtime)
    assert autotoolschain.msvc_runtime_flag == expected_flag
    env = autotoolschain.environment().vars(conanfile)
    assert expected_flag in env["CFLAGS"]
    assert expected_flag in env["CXXFLAGS"]


def test_get_gnu_triplet_for_cross_building_raise_error():
    """
    Testing AutotoolsToolchain and _get_gnu_triplet() function raises an error in case of
    having os=Windows, cross compiling and not defined any compiler
    """
    # Issue: https://github.com/conan-io/conan/issues/10139
    settings = MockSettings({"build_type": "Release",
                             "os": "Windows",
                             "arch": "x86_64"})
    conanfile = ConanFileMock()
    conanfile.settings = settings
    conanfile.settings_build = MockSettings({"os": "Solaris", "arch": "x86"})
    with pytest.raises(ConanException) as conan_error:
        AutotoolsToolchain(conanfile)
        msg = "'compiler' parameter for 'get_gnu_triplet()' is not specified and " \
              "needed for os=Windows"
        assert msg == str(conan_error.value)
