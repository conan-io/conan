import os

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


@pytest.mark.parametrize("requires", ["requires", "tool_requires"])
def test_conanfile_txt_deps_ranges(requires):
    """
    conanfile.txt locking it dependencies (with version ranges) using alias
    """
    client = TestClient()
    client.save({"pkg/conanfile.py": GenConanfile("pkg"),
                 "consumer/conanfile.txt": f"[{requires}]\npkg/(latest)"})
    client.run("create pkg --version=0.1")
    client.run("create pkg --version=0.2")
    with client.chdir("alias"):
        client.run("new alias -d name=pkg -d version=latest -d target=0.1")
        client.run("export .")
    client.run("lock create consumer/conanfile.txt")
    assert "pkg/0.1" in client.out
    assert '"pkg/latest": "pkg/0.1"' in client.load("consumer/conan.lock")

    # Change the alias
    with client.chdir("alias"):
        client.run("new alias -d name=pkg -d version=latest -d target=0.2 -f")
        client.run("export .")
    client.run("install consumer/conanfile.txt")  # use conan.lock by default
    assert "pkg/0.1" in client.out
    assert "pkg/0.2" not in client.out

    os.remove(os.path.join(client.current_folder, "consumer/conan.lock"))
    client.run("install consumer/conanfile.txt")
    assert "pkg/0.2" in client.out
    assert "pkg/0.1" not in client.out


@pytest.mark.parametrize("requires", ["requires", "tool_requires"])
def test_conanfile_txt_deps_ranges_lock_revisions(requires):
    """
    conanfile.txt locking it dependencies (with version ranges)
    """
    client = TestClient()
    client.save({"pkg/conanfile.py": GenConanfile("pkg"),
                 "consumer/conanfile.txt": f"[{requires}]\npkg/(latest)"})
    client.run("create pkg --version=0.1")
    client.assert_listed_require({"pkg/0.1#a9ec2e5fbb166568d4670a9cd1ef4b26": "Cache"})
    client.run("create pkg --version=0.2")
    with client.chdir("alias"):
        client.run("new alias -d name=pkg -d version=latest -d target=0.1")
        client.run("export .")
    client.run("lock create consumer/conanfile.txt")
    assert "pkg/0.1#a9ec2e5fbb166568d4670a9cd1ef4b26" in client.out
    assert '"pkg/latest": "pkg/0.1"' in client.load("consumer/conan.lock")

    # Create a new revision
    client.save({"pkg/conanfile.py": GenConanfile("pkg").with_class_attribute("potato=42")})
    client.run("create pkg --version=0.1")
    client.assert_listed_require({"pkg/0.1#8d60cd02b0b4aa8fe8b3cae32944c61b": "Cache"})
    client.run("install consumer/conanfile.txt")  # use conan.lock by default
    assert "pkg/0.1#a9ec2e5fbb166568d4670a9cd1ef4b26" in client.out
    assert "pkg/0.1#8d60cd02b0b4aa8fe8b3cae32944c61b" not in client.out

    os.remove(os.path.join(client.current_folder, "consumer/conan.lock"))
    client.run("install consumer/conanfile.txt")
    assert "pkg/0.1#a9ec2e5fbb166568d4670a9cd1ef4b26" not in client.out
    assert "pkg/0.1#8d60cd02b0b4aa8fe8b3cae32944c61b" in client.out
