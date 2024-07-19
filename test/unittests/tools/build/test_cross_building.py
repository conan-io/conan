import pytest

from conan.tools.build import cross_building
from conan.test.utils.mocks import ConanFileMock


@pytest.mark.parametrize("cross_build", (True, False))
def test_using_cross_build_conf(cross_build):
    """
    Tests cross_building function is using the conf variable to force or not.

    Issue related: https://github.com/conan-io/conan/issues/15392
    """
    conanfile = ConanFileMock()
    conanfile.conf.define("tools.build.cross_building:cross_build", cross_build)
    assert cross_building(conanfile) == cross_build
