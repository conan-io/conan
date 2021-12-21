import pytest

from conans.client.build.cmake_flags import get_generator
from conans.test.utils.mocks import ConanFileMock, MockSettings


@pytest.mark.parametrize("compiler,version,expected", [
    ("Visual Studio", "15", "Visual Studio 15 2017"),
    ("Visual Studio", "15.9", "Visual Studio 15 2017"),
    ("msvc", "193", "Visual Studio 17 2022"),
    ("msvc", "192", "Visual Studio 16 2019")
])
def test_vs_generator(compiler, version, expected):
    settings = MockSettings({"os": "Windows", "arch": "x86_64", "compiler": compiler})
    conanfile = ConanFileMock()
    conanfile.settings = settings

    settings.values['compiler.version'] = version
    assert get_generator(conanfile) == expected
