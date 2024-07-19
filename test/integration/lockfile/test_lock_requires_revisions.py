import textwrap

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


@pytest.mark.parametrize("requires", ["requires", "tool_requires"])
def test_conanfile_txt_deps_revisions(requires):
    """
    conanfile.txt locking it dependencies (with revisions)
    """
    client = TestClient()
    client.save({"pkg/conanfile.py": GenConanfile().with_package_id("self.output.info('REV1!!!!')"),
                 "consumer/conanfile.txt": f"[{requires}]\npkg/0.1@user/testing"})
    client.run("create pkg --name=pkg --version=0.1 --user=user --channel=testing")
    assert "REV1!!!" in client.out
    client.run("lock create consumer/conanfile.txt  --lockfile-out=consumer.lock")
    assert "pkg/0.1@user/testing#" in client.out

    client.save({"pkg/conanfile.py": GenConanfile().with_package_id("self.output.info('REV2!!!!')")})
    client.run("create pkg --name=pkg --version=0.1 --user=user --channel=testing")
    assert "REV2!!!" in client.out

    client.run("install consumer/conanfile.txt --lockfile=consumer.lock")
    assert "REV1!!!" in client.out
    assert "REV2!!!" not in client.out
    client.run("install consumer/conanfile.txt")
    assert "REV2!!!" in client.out
    assert "REV1!!!" not in client.out


@pytest.mark.parametrize("requires", ["requires", "tool_requires"])
@pytest.mark.parametrize("req_version", ["0.1", "[>=0.0]"])
def test_conanfile_txt_deps_revisions_transitive(requires, req_version):
    """
    conanfile.txt locking it dependencies and its transitive dependencies (with revisions)
    """
    client = TestClient()
    client.save({"dep/conanfile.py": GenConanfile().with_package_id("self.output.info('REV1!!!!')"),
                 "pkg/conanfile.py": GenConanfile().with_requires(f"dep/{req_version}@user/testing"),
                 "consumer/conanfile.txt": f"[{requires}]\npkg/{req_version}@user/testing"})
    client.run("create dep --name=dep --version=0.1 --user=user --channel=testing")
    assert "REV1!!!" in client.out
    client.run("create pkg --name=pkg --version=0.1 --user=user --channel=testing")

    client.run("lock create consumer/conanfile.txt  --lockfile-out=consumer.lock")
    assert "dep/0.1@user/testing#" in client.out
    assert "pkg/0.1@user/testing#" in client.out

    client.save({"dep/conanfile.py": GenConanfile().with_package_id("self.output.info('REV2!!!!')")})
    client.run("create dep --name=dep --version=0.1 --user=user --channel=testing")
    assert "REV2!!!" in client.out

    client.run("install consumer/conanfile.txt --lockfile=consumer.lock")
    assert "REV1!!!" in client.out
    assert "REV2!!!" not in client.out
    client.run("list dep/0.1@user/testing#*")
    client.run("install consumer/conanfile.txt")
    assert "REV2!!!" in client.out
    assert "REV1!!!" not in client.out


@pytest.mark.parametrize("requires", ["requires", "tool_requires"])
def test_conanfile_txt_strict_revisions(requires):
    """
    conanfile.txt locking it dependencies (with version ranges)
    """
    client = TestClient()
    client.save({"pkg/conanfile.py": GenConanfile().with_package_id("self.output.info('REV1!!!!')"),
                 "consumer/conanfile.txt": f"[{requires}]\npkg/0.1@user/testing"})
    client.run("create pkg --name=pkg --version=0.1 --user=user --channel=testing")
    client.run("lock create consumer/conanfile.txt")
    assert "pkg/0.1@user/testing#" in client.out

    client.save({"pkg/conanfile.py": GenConanfile().with_package_id("self.output.info('REV2!!!!')")})
    client.run("create pkg --name=pkg --version=0.1 --user=user --channel=testing")
    rrev = client.exported_recipe_revision()

    # Not strict mode works
    client.save({"consumer/conanfile.txt": f"[{requires}]\npkg/0.1@user/testing#{rrev}"})

    client.run("install consumer/conanfile.txt", assert_error=True)
    assert f"Requirement 'pkg/0.1@user/testing#{rrev}' not in lockfile" in client.out


@pytest.mark.parametrize("requires", ["requires", "tool_requires"])
def test_conditional_os(requires):
    """
    conanfile.txt can lock conditional dependencies (conditional on OS for example),
    with consecutive calls to "conan lock create", augmenting the lockfile
    """
    client = TestClient()

    pkg_conanfile = textwrap.dedent(f"""
        from conan import ConanFile
        class Pkg(ConanFile):
            settings = "os"
            def requirements(self):
                if self.settings.os == "Windows":
                    self.requires("win/0.1")
                else:
                    self.requires("nix/0.1")
        """)

    client.save({"dep/conanfile.py": GenConanfile().with_package_id("self.output.info('REV1!!!!')"),
                 "pkg/conanfile.py": pkg_conanfile,
                 "consumer/conanfile.txt": f"[{requires}]\npkg/0.1"})
    client.run("create dep --name=win --version=0.1")
    client.run("create dep --name=nix --version=0.1")

    client.run("create pkg --name=pkg --version=0.1 -s os=Windows")
    client.run("create pkg --name=pkg --version=0.1 -s os=Linux")

    client.run("lock create consumer/conanfile.txt  --lockfile-out=consumer.lock -s os=Windows"
               " -s:b os=Windows")
    assert "win/0.1#" in client.out
    assert "pkg/0.1#" in client.out
    client.run("lock create consumer/conanfile.txt  --lockfile=consumer.lock "
               "--lockfile-out=consumer.lock -s os=Linux -s:b os=Linux")
    assert "nix/0.1#" in client.out
    assert "pkg/0.1#" in client.out

    # New dependencies will not be used if using the lockfile
    client.save({"dep/conanfile.py": GenConanfile().with_package_id("self.output.info('REV2!!!!')")})
    client.run("create dep --name=win --version=0.1")
    client.run("create dep --name=nix --version=0.1")
    client.run("create pkg --name=pkg --version=0.1 -s os=Windows")
    client.run("create pkg --name=pkg --version=0.1 -s os=Linux")

    client.run("install consumer --lockfile=consumer.lock -s os=Windows -s:b os=Windows")
    assert "REV1!!!" in client.out
    assert "REV2!!!" not in client.out
    assert "nix/0.1" not in client.out
    client.run("install consumer -s os=Windows -s:b os=Windows")
    assert "REV2!!!" in client.out
    assert "REV1!!!" not in client.out
    assert "nix/0.1" not in client.out

    client.run("install consumer --lockfile=consumer.lock -s os=Linux -s:b os=Linux")
    assert "REV1!!!" in client.out
    assert "REV2!!!" not in client.out
    assert "win/0.1" not in client.out
    client.run("install consumer -s os=Linux -s:b os=Linux")
    assert "REV2!!!" in client.out
    assert "REV1!!!" not in client.out
    assert "win/0.1" not in client.out


@pytest.mark.parametrize("requires", ["requires", "tool_requires"])
def test_conditional_same_package_revisions(requires):
    # What happens when a conditional requires different versions of the same package?
    client = TestClient()

    pkg_conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            settings = "os"
            def requirements(self):
                if self.settings.os == "Windows":
                    self.requires("dep/0.1#{}")
                else:
                    self.requires("dep/0.1#{}")
        """)
    client.save({"dep1/conanfile.py": GenConanfile().with_package_id("self.output.info('REV1!!!!')"),
                 "dep2/conanfile.py": GenConanfile().with_package_id("self.output.info('REV2!!!!')"),
                 "pkg/conanfile.py": pkg_conanfile,
                 "consumer/conanfile.txt": f"[{requires}]\npkg/0.1"})
    client.run("create dep1 --name=dep --version=0.1")
    rrev1 = client.exported_recipe_revision()
    client.run("create dep2 --name=dep --version=0.1")
    rrev2 = client.exported_recipe_revision()
    client.save({"pkg/conanfile.py": pkg_conanfile.format(rrev1, rrev2)})

    client.run("create pkg --name=pkg --version=0.1 -s os=Windows")
    client.run("create pkg --name=pkg --version=0.1 -s os=Linux")

    client.run("lock create consumer/conanfile.txt  --lockfile-out=conan.lock -s os=Windows"
               " -s:b os=Windows")
    assert "REV1!!!" in client.out
    assert "REV2!!!" not in client.out
    client.run("lock create consumer/conanfile.txt  --lockfile=conan.lock "
               "--lockfile-out=conan.lock -s os=Linux -s:b os=Linux")
    assert "REV2!!!" in client.out
    assert "REV1!!!" not in client.out

    client.run("install consumer --lockfile=conan.lock --lockfile-out=win.lock -s os=Windows"
               " -s:b os=Windows")
    assert "REV1!!!" in client.out
    assert "REV2!!!" not in client.out

    client.run("install consumer --lockfile=conan.lock --lockfile-out=linux.lock -s os=Linux"
               " -s:b os=Linux")
    assert "REV2!!!" in client.out
    assert "REV1!!!" not in client.out
