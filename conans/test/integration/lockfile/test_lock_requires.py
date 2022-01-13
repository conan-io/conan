import textwrap

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


@pytest.mark.parametrize("requires", ["requires", "tool_requires"])
def test_conanfile_txt_deps_ranges(requires):
    """
    conanfile.txt locking it dependencies (with version ranges)
    """
    client = TestClient()
    client.save({"pkg/conanfile.py": GenConanfile(),
                 "consumer/conanfile.txt": f"[{requires}]\npkg/[>0.0]@user/testing"})
    client.run("create pkg pkg/0.1@user/testing")
    client.run("lock create consumer/conanfile.txt  --lockfile-out=conan.lock")
    assert "pkg/0.1@user/testing#" in client.out

    client.run("create pkg pkg/0.2@user/testing")

    client.run("install consumer/conanfile.txt --lockfile=conan.lock")
    assert "pkg/0.1@user/testing#" in client.out
    assert "pkg/0.2" not in client.out
    client.run("install consumer/conanfile.txt")
    assert "pkg/0.2@user/testing#" in client.out
    assert "pkg/0.1" not in client.out


@pytest.mark.parametrize("requires", ["requires", "tool_requires"])
def test_conanfile_txt_deps_ranges_transitive(requires):
    """
    conanfile.txt locking it dependencies and its transitive dependencies (with version ranges)
    """
    client = TestClient()
    client.save({"dep/conanfile.py": GenConanfile(),
                 "pkg/conanfile.py": GenConanfile().with_requires("dep/[>0.0]@user/testing"),
                 "consumer/conanfile.txt": f"[{requires}]\npkg/[>0.0]@user/testing"})
    client.run("create dep dep/0.1@user/testing")
    client.run("create pkg pkg/0.1@user/testing")

    client.run("lock create consumer/conanfile.txt  --lockfile-out=conan.lock")
    assert "dep/0.1@user/testing#" in client.out
    assert "pkg/0.1@user/testing#" in client.out

    client.run("create dep dep/0.2@user/testing")

    client.run("install consumer/conanfile.txt --lockfile=conan.lock")
    assert "dep/0.1@user/testing#" in client.out
    assert "dep/0.2" not in client.out
    client.run("install consumer/conanfile.txt", assert_error=True)
    assert "dep/0.2@user/testing#" in client.out
    assert "dep/0.1" not in client.out


@pytest.mark.parametrize("requires", ["requires", "tool_requires"])
def test_conanfile_txt_strict(requires):
    """
    conanfile.txt locking it dependencies (with version ranges)
    """
    client = TestClient()
    client.save({"pkg/conanfile.py": GenConanfile(),
                 "consumer/conanfile.txt": f"[{requires}]\npkg/[>0.0]@user/testing"})
    client.run("create pkg pkg/0.1@user/testing")
    client.run("lock create consumer/conanfile.txt  --lockfile-out=conan.lock")
    assert "pkg/0.1@user/testing#" in client.out

    client.run("create pkg pkg/0.2@user/testing")
    client.run("create pkg pkg/1.2@user/testing")

    # Not strict mode works
    client.save({"consumer/conanfile.txt": f"[{requires}]\npkg/[>1.0]@user/testing"})

    client.run("install consumer/conanfile.txt --lockfile=conan.lock", assert_error=True)
    assert "Requirement 'pkg/[>1.0]@user/testing' not in lockfile" in client.out


@pytest.mark.parametrize("requires", ["requires", "tool_requires"])
def test_conditional_os(requires):
    """
    conanfile.txt can lock conditional dependencies (conditional on OS for example),
    with consecutive calls to "conan lock create", augmenting the lockfile
    """
    client = TestClient()

    pkg_conanfile = textwrap.dedent(f"""
        from conans import ConanFile
        class Pkg(ConanFile):
            settings = "os"
            def requirements(self):
                if self.settings.os == "Windows":
                    self.requires("win/[>0.0]")
                else:
                    self.requires("nix/[>0.0]")
        """)
    client.save({"dep/conanfile.py": GenConanfile(),
                 "pkg/conanfile.py": pkg_conanfile,
                 "consumer/conanfile.txt": f"[{requires}]\npkg/0.1"})
    client.run("create dep win/0.1@")
    client.run("create dep nix/0.1@")

    client.run("create pkg pkg/0.1@ -s os=Windows")
    client.run("create pkg pkg/0.1@ -s os=Linux")

    client.run("lock create consumer/conanfile.txt  --lockfile-out=conan.lock -s os=Windows"
               " -s:b os=Windows")
    assert "win/0.1#" in client.out
    assert "pkg/0.1#" in client.out
    client.run("lock create consumer/conanfile.txt  --lockfile=conan.lock "
               "--lockfile-out=conan.lock -s os=Linux -s:b os=Linux")
    assert "nix/0.1#" in client.out
    assert "pkg/0.1#" in client.out

    # New dependencies will not be used if using the lockfile
    client.run("create dep win/0.2@")
    client.run("create dep nix/0.2@")
    client.run("create pkg pkg/0.1@ -s os=Windows")
    client.run("create pkg pkg/0.1@ -s os=Linux")

    client.run("install consumer --lockfile=conan.lock -s os=Windows -s:b os=Windows")
    assert "win/0.1#" in client.out
    assert "win/0.2" not in client.out
    client.run("install consumer -s os=Windows -s:b os=Windows")
    assert "win/0.2#" in client.out
    assert "win/0.1" not in client.out
    assert "nix/0.1" not in client.out

    client.run("install consumer --lockfile=conan.lock -s os=Linux -s:b os=Linux")
    assert "nix/0.1#" in client.out
    assert "nix/0.2" not in client.out
    client.run("install consumer -s os=Linux -s:b os=Linux")
    assert "nix/0.2#" in client.out
    assert "nix/0.1" not in client.out
    assert "win" not in client.out


@pytest.mark.parametrize("requires", ["requires", "tool_requires"])
def test_conditional_same_package(requires):
    # What happens when a conditional requires different versions of the same package?
    client = TestClient()

    pkg_conanfile = textwrap.dedent("""
        from conans import ConanFile
        class Pkg(ConanFile):
            settings = "os"
            def requirements(self):
                if self.settings.os == "Windows":
                    self.requires("dep/0.1")
                else:
                    self.requires("dep/0.2")
        """)
    client.save({"dep/conanfile.py": GenConanfile(),
                 "pkg/conanfile.py": pkg_conanfile,
                 "consumer/conanfile.txt": f"[{requires}]\npkg/0.1"})
    client.run("create dep dep/0.1@")
    client.run("create dep dep/0.2@")

    client.run("create pkg pkg/0.1@ -s os=Windows")
    client.run("create pkg pkg/0.1@ -s os=Linux")

    client.run("lock create consumer/conanfile.txt  --lockfile-out=conan.lock -s os=Windows"
               " -s:b os=Windows")
    assert "dep/0.1#" in client.out
    assert "dep/0.2" not in client.out
    client.run("lock create consumer/conanfile.txt  --lockfile=conan.lock "
               "--lockfile-out=conan.lock -s os=Linux -s:b os=Linux")
    assert "dep/0.2#" in client.out
    assert "dep/0.1" not in client.out

    client.run("install consumer --lockfile=conan.lock --lockfile-out=win.lock -s os=Windows"
               " -s:b os=Windows")
    assert "dep/0.1#" in client.out
    assert "dep/0.2" not in client.out

    client.run("install consumer --lockfile=conan.lock --lockfile-out=linux.lock -s os=Linux"
               " -s:b os=Linux")
    assert "dep/0.2#" in client.out
    assert "dep/0.1" not in client.out


@pytest.mark.parametrize("requires", ["requires", "build_requires"])
def test_conditional_incompatible_range(requires):
    client = TestClient()

    pkg_conanfile = textwrap.dedent("""
        from conans import ConanFile
        class Pkg(ConanFile):
            settings = "os"
            def requirements(self):
                if self.settings.os == "Windows":
                    self.requires("dep/[<1.0]")
                else:
                    self.requires("dep/[>=1.0]")
        """)
    client.save({"dep/conanfile.py": GenConanfile(),
                 "pkg/conanfile.py": pkg_conanfile,
                 "consumer/conanfile.txt": "[requires]\npkg/0.1"})
    client.run("create dep dep/0.1@")
    client.run("create dep dep/1.1@")

    client.run("create pkg pkg/0.1@ -s os=Windows")
    client.run("create pkg pkg/0.1@ -s os=Linux")

    client.run("lock create consumer/conanfile.txt  --lockfile-out=conan.lock -s os=Windows"
               " -s:b os=Windows")
    assert "dep/0.1#" in client.out
    assert "dep/1.1" not in client.out
    # The previous lock was locking dep/0.1. This new lock will not use dep/0.1 as it is outside
    # of its range, can't lock to it and will depend on dep/1.1. Both dep/0.1 for Windows and
    # dep/1.1 for Linux now coexist in the lock
    client.run("lock create consumer/conanfile.txt  --lockfile=conan.lock "
               "--lockfile-out=conan.lock -s os=Linux -s:b os=Linux")
    assert "dep/1.1#" in client.out
    assert "dep/0.1" not in client.out
    lock = client.load("conan.lock")
    assert "dep/0.1" in lock
    assert "dep/1.1" in lock

    # These will not be used, lock will avoid them
    client.run("create dep dep/0.2@")
    client.run("create dep dep/1.2@")

    client.run("install consumer --lockfile=conan.lock --lockfile-out=win.lock -s os=Windows"
               " -s:b os=Windows")
    assert "dep/0.1#" in client.out
    assert "dep/1.1" not in client.out

    client.run("install consumer --lockfile=conan.lock --lockfile-out=linux.lock -s os=Linux"
               " -s:b os=Linux")
    assert "dep/1.1#" in client.out
    assert "dep/0.1" not in client.out


@pytest.mark.parametrize("requires", ["requires", "tool_requires"])
def test_conditional_compatible_range(requires):
    client = TestClient()

    pkg_conanfile = textwrap.dedent("""
        from conans import ConanFile
        class Pkg(ConanFile):
            settings = "os"
            def requirements(self):
                if self.settings.os == "Windows":
                    self.requires("dep/[<0.2]")
                else:
                    self.requires("dep/[>0.0]")
        """)
    client.save({"dep/conanfile.py": GenConanfile(),
                 "pkg/conanfile.py": pkg_conanfile,
                 "consumer/conanfile.txt": f"[{requires}]\npkg/0.1"})
    client.run("create dep dep/0.1@")
    client.run("create dep dep/0.2@")

    client.run("create pkg pkg/0.1@ -s os=Windows")
    client.run("create pkg pkg/0.1@ -s os=Linux")

    client.run("lock create consumer/conanfile.txt  --lockfile-out=conan.lock -s os=Linux"
               " -s:b os=Linux")
    assert "dep/0.2#" in client.out
    assert "dep/0.1" not in client.out
    client.run("lock create consumer/conanfile.txt  --lockfile=conan.lock "
               "--lockfile-out=conan.lock -s os=Windows -s:b os=Windows")
    assert "dep/0.1#" in client.out
    assert "dep/0.2" not in client.out

    # These will not be used, lock will avoid them
    client.run("create dep dep/0.1.1@")
    client.run("create dep dep/0.3@")

    client.run("install consumer --lockfile=conan.lock --lockfile-out=win.lock -s os=Windows"
               " -s:b os=Windows")
    assert "dep/0.1#" in client.out
    assert "dep/0.2" not in client.out
    assert "dep/0.1.1" not in client.out

    client.run("install consumer --lockfile=conan.lock --lockfile-out=linux.lock -s os=Linux "
               " -s:b os=Linux")
    assert "dep/0.2#" in client.out
    assert "dep/0.1" not in client.out
    assert "dep/0.3" not in client.out
