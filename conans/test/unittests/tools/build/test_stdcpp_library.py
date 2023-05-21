import pytest
from conan.tools.build import stdcpp_library
from conans.test.utils.mocks import MockSettings, MockConanfile


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
    conanfile = MockConanfile(settings)

    assert stdcpp_library(conanfile) == expected_library
