import re

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID


def test_private_skip():
    # app -> pkg -(private)-> dep
    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . --name=dep --version=1.0")
    client.save({"conanfile.py": GenConanfile().with_requirement("dep/1.0", visible=False)})
    client.run("create . --name=pkg --version=1.0")
    client.run("remove dep/1.0 -p -f")  # Dep binary is removed not used at all

    client.save({"conanfile.py": GenConanfile().with_requires("pkg/1.0")})
    client.run("create . --name=app --version=1.0")
    assert f"dep/1.0:{NO_SETTINGS_PACKAGE_ID} - Skip" in client.out


def test_private_no_skip():
    # app -> pkg -(private)-> dep
    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . --name=dep --version=1.0")
    client.save({"conanfile.py": GenConanfile().with_requirement("dep/1.0", visible=False)})
    client.run("create . --name=pkg --version=1.0")

    # But if we want to build pkg, no skip
    client.run("create . --name=app --version=1.0 --build=app --build=pkg")
    assert f"dep/1.0:{NO_SETTINGS_PACKAGE_ID} - Cache" in client.out

    client.run("remove dep/1.0 -p -f")  # Dep binary is removed not used at all
    client.run("create . --name=app --version=1.0 --build=app --build=pkg", assert_error=True)
    assert f"dep/1.0:{NO_SETTINGS_PACKAGE_ID} - Missing" in client.out


def test_consumer_no_skip():
    # app -(private)-> pkg -> dep
    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . --name=dep --version=1.0")
    client.save({"conanfile.py": GenConanfile().with_requires("dep/1.0")})
    client.run("create . --name=pkg --version=1.0")
    package_id = re.search(r"pkg/1.0:(\S+)", str(client.out)).group(1)
    client.save({"conanfile.py": GenConanfile().with_requirement("pkg/1.0", visible=False)})

    client.run("install . ")

    client.assert_listed_binary({f"dep/1.0": (NO_SETTINGS_PACKAGE_ID, "Cache")})
    client.assert_listed_binary({f"pkg/1.0": (package_id, "Cache")})


def test_shared_link_static_skip():
    # app -> pkg (shared) -> dep (static)
    client = TestClient()
    client.save({"conanfile.py": GenConanfile().with_shared_option(False)})
    client.run("create . --name=dep --version=1.0")
    package_id = re.search(r"dep/1.0:(\S+)", str(client.out)).group(1)
    client.save({"conanfile.py": GenConanfile().with_requirement("dep/1.0").
                with_shared_option(True)})
    client.run("create . --name=pkg --version=1.0")
    client.run("remove dep/1.0 -p -f")  # Dep binary is removed not used at all

    client.save({"conanfile.py": GenConanfile().with_requires("pkg/1.0")})
    client.run("create . --name=app --version=1.0")
    assert f"dep/1.0:{package_id} - Skip" in client.out
