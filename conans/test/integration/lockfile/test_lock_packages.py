import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID


@pytest.mark.parametrize("requires", ["requires", "tool_requires"])
def test_conanfile_txt_deps_ranges(requires):
    """
    Check that package revisions can be locked too
    NOTE: They are still not used! only to check that it is possible to store them
          And that the lockfile is still usable
    """
    client = TestClient()
    client.save({"pkg/conanfile.py": GenConanfile(),
                 "consumer/conanfile.txt": f"[{requires}]\npkg/[>0.0]"})
    client.run("create pkg --name=pkg --version=0.1 ")
    client.run("lock create consumer/conanfile.txt  --lockfile-out=conan.lock --lockfile-packages")
    assert "pkg/0.1#" in client.out
    lock = client.load("conan.lock")
    assert NO_SETTINGS_PACKAGE_ID in lock

    client.run("create pkg --name=pkg --version=0.2 ")

    client.run("install consumer/conanfile.txt --lockfile=conan.lock")
    assert "pkg/0.1#" in client.out
    assert "pkg/0.2" not in client.out
    client.run("install consumer/conanfile.txt")
    assert "pkg/0.2#" in client.out
    assert "pkg/0.1" not in client.out
