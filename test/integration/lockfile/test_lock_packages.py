import os

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID
from conan.test.utils.env import environment_update


@pytest.mark.parametrize("requires", ["requires", "tool_requires"])
def test_lock_packages(requires):
    """
    Check that package revisions can be locked too
    NOTE: They are still not used! only to check that it is possible to store them
          And that the lockfile is still usable
    """
    client = TestClient()
    client.save({"pkg/conanfile.py": GenConanfile().with_package_file("file.txt", env_var="MYVAR"),
                 "consumer/conanfile.txt": f"[{requires}]\npkg/[>0.0]"})
    with environment_update({"MYVAR": "MYVALUE"}):
        client.run("create pkg --name=pkg --version=0.1")
    prev = client.created_package_revision("pkg/0.1")

    client.run("lock create consumer/conanfile.txt --lockfile-packages")
    assert "ERROR: The --lockfile-packages arg is private and shouldn't be used" in client.out
    assert "pkg/0.1#" in client.out
    lock = client.load("consumer/conan.lock")
    assert NO_SETTINGS_PACKAGE_ID in lock

    with environment_update({"MYVAR": "MYVALUE2"}):
        client.run("create pkg --name=pkg --version=0.1")
    prev2 = client.created_package_revision("pkg/0.1")
    assert prev2 != prev

    client.run("install consumer/conanfile.txt")
    assert prev in client.out
    assert prev2 not in client.out

    os.remove(os.path.join(client.current_folder, "consumer/conan.lock"))
    client.run("install consumer/conanfile.txt")
    assert prev2 in client.out
    assert prev not in client.out
