import pytest

from conan.tools.build import cross_building
from conans.test.utils.mocks import ConanFileMock


@pytest.mark.parametrize("force", (True, False))
def test_using_force_conf(force):
    """
    Tests cross_building function is using the conf variable to force or not.

    Issue related: https://github.com/conan-io/conan/issues/15392
    """
    conanfile = ConanFileMock()
    conanfile.conf.define("tools.build.cross_building:force", force)
    assert cross_building(conanfile) == force
