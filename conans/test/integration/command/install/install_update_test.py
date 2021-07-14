import os
import textwrap
import time
from collections import OrderedDict
from time import sleep

import pytest

from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import CONAN_MANIFEST
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, TestServer, \
    TurboTestClient, GenConanfile
from conans.util.files import load, save


def test_update_binaries():
    client = TestClient(default_server_user=True)
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conans.tools import save
        import os, random
        class Pkg(ConanFile):
            def package(self):
                save(os.path.join(self.package_folder, "file.txt"), str(random.random()))
            def deploy(self):
                self.copy("file.txt")
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create . Pkg/0.1@lasote/testing")
    client.run("upload Pkg/0.1@lasote/testing --all")

    client2 = TestClient(servers=client.servers, users=client.users)
    client2.run("install Pkg/0.1@lasote/testing")
    value = load(os.path.join(client2.current_folder, "file.txt"))

    time.sleep(1)  # Make sure the new timestamp is later
    client.run("create . Pkg/0.1@lasote/testing")
    client.run("upload Pkg/0.1@lasote/testing --all")

    client2.run("install Pkg/0.1@lasote/testing")
    new_value = load(os.path.join(client2.current_folder, "file.txt"))
    assert value == new_value

    client2.run("install Pkg/0.1@lasote/testing --update")
    assert "Current package is older than remote upstream one" in client2.out
    new_value = load(os.path.join(client2.current_folder, "file.txt"))
    assert value != new_value

    # Now check newer local modifications are not overwritten
    time.sleep(1)  # Make sure the new timestamp is later
    client.run("create . Pkg/0.1@lasote/testing")
    client.run("upload Pkg/0.1@lasote/testing --all")

    client2.save({"conanfile.py": conanfile})
    client2.run("create . Pkg/0.1@lasote/testing")
    client2.run("install Pkg/0.1@lasote/testing")
    value2 = load(os.path.join(client2.current_folder, "file.txt"))
    client2.run("install Pkg/0.1@lasote/testing --update -r default")
    assert "Current package is newer than remote upstream one" in client2.out
    new_value = load(os.path.join(client2.current_folder, "file.txt"))
    assert value2 == new_value


def test_update_not_date():
    client = TestClient(default_server_user=True)
    # Regression for https://github.com/conan-io/conan/issues/949
    client.save({"conanfile.py": GenConanfile("Hello0", "1.0")})
    client.run("export . lasote/stable")
    client.save({"conanfile.py": GenConanfile("Hello1", "1.0").
                with_requirement("Hello0/1.0@lasote/stable")},
                clean_first=True)
    client.run("install . --build")
    client.run("upload Hello0/1.0@lasote/stable --all")

    client.run("remote list_ref")
    assert "Hello0/1.0@lasote/stable" in client.out
    client.run("remote list_pref Hello0/1.0@lasote/stable")
    prev = client.get_latest_prev("Hello0/1.0@lasote/stable")
    package_reference = f"Hello0/1.0@lasote/stable#{prev.ref.revision}:{prev.id}"
    assert package_reference in client.out

    ref = ConanFileReference.loads("Hello0/1.0@lasote/stable")
    export_folder = client.get_latest_ref_layout(ref).export()
    recipe_manifest = os.path.join(export_folder, CONAN_MANIFEST)
    package_folder = client.cache.pkg_layout(prev).package()
    package_manifest = os.path.join(package_folder, CONAN_MANIFEST)

    initial_recipe_timestamp = client.cache.get_timestamp(client.cache.get_latest_rrev(ref))
    initial_package_timestamp = client.cache.get_timestamp(prev)

    time.sleep(1)

    # Change and rebuild package
    client.save({"conanfile.py": GenConanfile("Hello0", "1.0").with_test("pass")}, clean_first=True)
    client.run("export . lasote/stable")
    client.run("install Hello0/1.0@lasote/stable --build")

    client.run("remote list_ref")
    assert "Hello0/1.0@lasote/stable" in client.out

    client.run("remote list_pref Hello0/1.0@lasote/stable")
    assert f"Hello0/1.0@lasote/stable#{prev.ref.revision}:{prev.id}" in client.out

    rebuild_recipe_timestamp = client.cache.get_timestamp(client.cache.get_latest_rrev(ref))
    rebuild_package_timestamp = client.cache.get_timestamp(client.get_latest_prev(ref))

    assert rebuild_recipe_timestamp != initial_recipe_timestamp
    assert rebuild_package_timestamp != initial_package_timestamp

    # back to the consumer, try to update
    client.save({"conanfile.py": GenConanfile("Hello1", "1.0").
                with_requirement("Hello0/1.0@lasote/stable")}, clean_first=True)
    # First assign the preference to a remote, it has been cleared when exported locally
    client.run("install . --update")
    # *1 With revisions here is removing the package because it doesn't belong to the recipe

    assert "Hello0/1.0@lasote/stable from local cache - Newer" in client.out

    failed_update_recipe_timestamp = client.cache.get_timestamp(client.cache.get_latest_rrev(ref))
    failed_update_package_timestamp = client.cache.get_timestamp(client.get_latest_prev(ref))

    assert rebuild_recipe_timestamp == failed_update_recipe_timestamp
    assert rebuild_package_timestamp == failed_update_package_timestamp


def test_reuse():
    client = TestClient(default_server_user=True)
    conanfile = GenConanfile("Hello0", "1.0").with_exports("*").with_package("self.copy('*')")
    client.save({"conanfile.py": conanfile,
                 "header.h": "content1"})
    client.run("export . lasote/stable")
    client.run("install Hello0/1.0@lasote/stable --build")
    client.run("upload Hello0/1.0@lasote/stable --all")

    client2 = TestClient(servers=client.servers, users=client.users)
    client2.run("install Hello0/1.0@lasote/stable")

    assert str(client2.out).count("Downloading conaninfo.txt") == 1

    client.save({"header.h": "//EMPTY!"})
    sleep(1)
    client.run("export . lasote/stable")
    client.run("install Hello0/1.0@lasote/stable --build")
    client.run("upload Hello0/1.0@lasote/stable --all")

    client2.run("install Hello0/1.0@lasote/stable --update")
    ref = ConanFileReference.loads("Hello0/1.0@lasote/stable")
    pref = client.get_latest_prev(ref)
    package_path = client2.get_latest_pkg_layout(pref).package()
    header = load(os.path.join(package_path, "header.h"))
    assert header == "//EMPTY!"


def test_upload_doesnt_follow_pref():
    servers = OrderedDict()
    servers['r1'] = TestServer()
    servers['r2'] = TestServer()
    client = TestClient(servers=servers, users={"r1": [("lasote", "mypass")],
                                                "r2": [("lasote", "mypass")]})
    ref = "Pkg/0.1@lasote/testing"
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . Pkg/0.1@lasote/testing")
    client.run("upload Pkg/0.1@lasote/testing --all -r r2")
    client.run("remote list_pref Pkg/0.1@lasote/testing")
    rrev = client.cache.get_latest_rrev(ConanFileReference.loads(ref))
    prev = client.cache.get_latest_prev(PackageReference(rrev, NO_SETTINGS_PACKAGE_ID))
    assert "%s: r2" % prev.full_str() in client.out
    client.run("remote remove_ref Pkg/0.1@lasote/testing")

    # It should upload both to r1 (default), not taking into account the pref to r2
    client.run("upload Pkg/0.1@lasote/testing --all")
    assert "Uploading package 1/1: %s to 'r1'" % NO_SETTINGS_PACKAGE_ID in client.out


def test_install_update_following_pref():
    conanfile = textwrap.dedent("""
        import os, random
        from conans import ConanFile, tools
        class Pkg(ConanFile):
            def package(self):
                tools.save(os.path.join(self.package_folder, "file.txt"), str(random.random()))
        """)
    servers = OrderedDict()
    servers["r1"] = TestServer()
    servers["r2"] = TestServer()
    client = TestClient(servers=servers, users={"r1": [("lasote", "mypass")],
                                                "r2": [("lasote", "mypass")]})

    ref = "Pkg/0.1@lasote/testing"
    client.save({"conanfile.py": conanfile})
    client.run("create . %s" % ref)
    client.run("upload %s --all -r r2" % ref)
    client.run("upload %s --all -r r1" % ref)
    # Force recipe to follow r1
    client.run("remote update_ref %s r1" % ref)

    # Update package in r2 from a different client
    time.sleep(1)
    client2 = TestClient(servers=servers, users=client.users)
    ref = "Pkg/0.1@lasote/testing"
    client2.save({"conanfile.py": conanfile})
    client2.run("create . %s" % ref)
    client2.run("upload %s --all -r r2" % ref)

    # Update from client, it will get the binary from r2
    client.run("install %s --update" % ref)
    assert "Pkg/0.1@lasote/testing from 'r1' - Cache" in client.out
    assert "Retrieving package %s from remote 'r2'" % NO_SETTINGS_PACKAGE_ID in client.out


def test_update_binaries_failed():
    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . Pkg/0.1@lasote/testing")
    client.run("install Pkg/0.1@lasote/testing --update")
    assert "Pkg/0.1@lasote/testing: WARN: Can't update, no remote defined" in client.out


def test_update_binaries_no_package_error():
    client = TestClient(default_server_user=True)
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . Pkg/0.1@lasote/testing")
    client.run("upload Pkg/0.1@lasote/testing")
    client.run("remote add_pref Pkg/0.1@lasote/testing:%s default" % NO_SETTINGS_PACKAGE_ID)
    client.run("install Pkg/0.1@lasote/testing --update")
    assert "Pkg/0.1@lasote/testing: WARN: Can't update, no package in remote" in client.out


def test_fail_usefully_when_failing_retrieving_package():
    ref = ConanFileReference.loads("lib/1.0@conan/stable")
    ref2 = ConanFileReference.loads("lib2/1.0@conan/stable")
    client = TurboTestClient(servers={"default": TestServer()})
    pref1 = client.create(ref)
    client.upload_all(ref)

    client.create(ref2, conanfile=GenConanfile().with_requirement(ref))
    client.upload_all(ref2)

    # remove only the package from pref1
    client.run("remove {} -p {} -f".format(pref1.ref, pref1.id))

    # Now fake the remote url to force a network failure
    client.run("remote update default http://this_not_exist8823.com")
    # Try to install ref2, it will try to download the binary for ref1
    client.run("install {}".format(ref2), assert_error=True)
    assert "ERROR: Error downloading binary package: '{}'".format(pref1) in client.out
