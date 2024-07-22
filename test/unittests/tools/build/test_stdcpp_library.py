import pytest
from conan.tools.build import stdcpp_library
from conan.test.utils.mocks import MockSettings, ConanFileMock


@pytest.mark.parametrize("libcxx,expected_library", [
    ("libstdc++", "stdc++"),
    ("libstdc++11", "stdc++"),
    ("libc++", "c++"),
    ("c++_shared", "c++_shared"),
    ("c++_static", "c++_static"),
    ("foobar", None)
])
def test_stdcpp_library(libcxx, expected_library):
    settings = MockSettings({"compiler.libcxx": libcxx})
    conanfile = ConanFileMock(settings)

    assert stdcpp_library(conanfile) == expected_library
