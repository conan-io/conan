import os
import textwrap

from conans.model.ref import ConanFileReference
from conans.paths import CONANFILE
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_conan_test():
    # Checks --build in test command
    client = TestClient()
    client.save({"conanfile.py": GenConanfile("Hello0", "0.0")})
    client.run("export . lasote/stable")
    client.save({"conanfile.py": GenConanfile("Hello1", "1.1").
                with_require("Hello0/0.0@lasote/stable")})
    client.run("export . lasote/stable")

    # Now test out Hello2
    client.save({"conanfile.py": GenConanfile("Hello2", "2.2").
                with_require("Hello1/1.1@lasote/stable"),
                 "test/conanfile.py": GenConanfile().with_test("pass")})

    # Should recognize the hello package
    # Will Fail because Hello0/0.0 and Hello1/1.1 has not built packages
    # and by default no packages are built
    client.run("create . lasote/stable", assert_error=True)
    assert "Try to build from sources with '--build=Hello0 --build=Hello1'" in client.out

    # We generate the package for Hello0/0.0
    client.run("install Hello0/0.0@lasote/stable --build Hello0")

    # Still missing Hello1/1.1
    client.run("create . lasote/stable", assert_error=True)
    assert "Try to build from sources with '--build=Hello1'" in client.out

    # We generate the package for Hello1/1.1
    client.run("install Hello1/1.1@lasote/stable --build Hello1")

    # Now Hello2 should be built and not fail
    client.run("create . lasote/stable")
    assert "Can't find a 'Hello2/2.2@lasote/stable' package" not in client.out
    assert 'Hello2/2.2@lasote/stable: Forced build from source' in client.out

    # Now package is generated but should be built again
    client.run("create . lasote/stable")
    assert 'Hello2/2.2@lasote/stable: Forced build from source' in client.out


def test_build_policies_update():
    client = TestClient(default_server_user=True)
    conanfile = textwrap.dedent("""
    from conans import ConanFile

    class MyPackage(ConanFile):
       name = "test"
       version = "1.9"
       build_policy = 'always'

       def source(self):
           self.output.info("Getting sources")
       def build(self):
           self.output.info("Building sources")
       def package(self):
           self.output.info("Packaging this test package")
       """)
    files = {CONANFILE: conanfile}
    client.save(files, clean_first=True)
    client.run("export . lasote/stable")
    client.run("install test/1.9@lasote/stable")
    assert "Getting sources" in client.out
    assert "Building sources" in client.out
    assert "Packaging this test package" in client.out
    assert "Building package from source as defined by build_policy='always'" in client.out
    client.run("upload test/1.9@lasote/stable")


def test_build_policies_in_conanfile():
    client = TestClient(default_server_user=True)
    base = GenConanfile("Hello0", "1.0").with_exports("*")
    conanfile = str(base) + "\n    build_policy = 'missing'"
    client.save({"conanfile.py": conanfile})
    client.run("export . lasote/stable")

    # Install, it will build automatically if missing (without the --build missing option)
    client.run("install Hello0/1.0@lasote/stable")
    assert "Building" in client.out

    # Try to do it again, now we have the package, so no build is done
    client.run("install Hello0/1.0@lasote/stable")
    assert "Building" not in client.out

    # Try now to upload all packages, should not crash because of the "missing" build policy
    client.run("upload Hello0/1.0@lasote/stable --all")

    #  --- Build policy to always ---
    conanfile = str(base) + "\n    build_policy = 'always'"
    client.save({"conanfile.py": conanfile}, clean_first=True)
    client.run("export . lasote/stable")

    # Install, it will build automatically if missing (without the --build missing option)
    client.run("install Hello0/1.0@lasote/stable")
    assert "Detected build_policy 'always', trying to remove source folder" in client.out
    assert "Building" in client.out

    # Try to do it again, now we have the package, but we build again
    client.run("install Hello0/1.0@lasote/stable")
    assert "Building" in client.out
    assert "Detected build_policy 'always', trying to remove source folder" in client.out

    # Try now to upload all packages, should crash because of the "always" build policy
    client.run("upload Hello0/1.0@lasote/stable --all", assert_error=True)
    assert "no packages can be uploaded" in client.out


def test_reuse():
    client = TestClient(default_server_user=True)
    client.save({"conanfile.py": GenConanfile("Hello0", "0.1")})
    client.run("export . lasote/stable")
    ref = ConanFileReference.loads("Hello0/0.1@lasote/stable")
    client.run("install %s --build missing" % str(ref))

    pkg_layout = client.get_latest_pkg_layout(ref)
    assert os.path.exists(pkg_layout.build())
    assert os.path.exists(pkg_layout.package())

    # Upload
    client.run("upload %s --all" % str(ref))

    # Now from other "computer" install the uploaded conans with same options (nothing)
    other_client = TestClient(servers=client.servers, users=client.users)
    other_client.run("install %s --build missing" % str(ref))

    pkg_layout = other_client.get_latest_pkg_layout(ref)
    assert not os.path.exists(pkg_layout.build())
    assert os.path.exists(pkg_layout.package())

    # Now from other "computer" install the uploaded conans with same options (nothing)
    other_client = TestClient(servers=client.servers, users=client.users)
    other_client.run("install %s --build" % str(ref))

    pkg_layout = other_client.get_latest_pkg_layout(ref)
    assert os.path.exists(pkg_layout.build())
    assert os.path.exists(pkg_layout.package())

    # Use an invalid pattern and check that its not builded from source
    other_client = TestClient(servers=client.servers, users=client.users)
    other_client.run("install %s --build HelloInvalid" % str(ref))

    pkg_layout = other_client.get_latest_pkg_layout(ref)
    assert "No package matching 'HelloInvalid' pattern" in other_client.out
    assert not os.path.exists(pkg_layout.build())

    # Use another valid pattern and check that its not builded from source
    other_client = TestClient(servers=client.servers, users=client.users)
    other_client.run("install %s --build HelloInvalid -b Hello" % str(ref))
    assert "No package matching 'HelloInvalid' pattern" in other_client.out

    # Now even if the package is in local store, check that's rebuilded
    other_client.run("install %s -b Hello*" % str(ref))
    assert "Copying sources to build folder" in other_client.out

    other_client.run("install %s" % str(ref))
    assert "Copying sources to build folder" not in other_client.out
