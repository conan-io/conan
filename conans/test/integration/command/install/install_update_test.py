import os
import textwrap
import time
from collections import OrderedDict
from time import sleep

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
    client2.run("install Pkg/0.1@lasote/testing --update")
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
    package_reference = "Hello0/1.0@lasote/stable:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"
    assert package_reference in client.out

    ref = ConanFileReference.loads("Hello0/1.0@lasote/stable")
    pref = PackageReference(ref, "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
    export_folder = client.cache.package_layout(ref).export()
    recipe_manifest = os.path.join(export_folder, CONAN_MANIFEST)
    package_folder = client.cache.package_layout(pref.ref).package(pref)
    package_manifest = os.path.join(package_folder, CONAN_MANIFEST)

    def timestamps():
        recipe_timestamp = load(recipe_manifest).splitlines()[0]
        package_timestamp = load(package_manifest).splitlines()[0]
        return recipe_timestamp, package_timestamp

    initial_timestamps = timestamps()

    time.sleep(1)

    # Change and rebuild package
    client.save({"conanfile.py": GenConanfile("Hello0", "1.0").with_test("pass")}, clean_first=True)
    client.run("export . lasote/stable")
    client.run("install Hello0/1.0@lasote/stable --build")

    client.run("remote list_ref")
    assert "Hello0/1.0@lasote/stable" in client.out

    client.run("remote list_pref Hello0/1.0@lasote/stable")
    assert "Hello0/1.0@lasote/stable:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9" in client.out

    rebuild_timestamps = timestamps()
    assert rebuild_timestamps != initial_timestamps

    # back to the consumer, try to update
    client.save({"conanfile.py": GenConanfile("Hello1", "1.0").
                with_requirement("Hello0/1.0@lasote/stable")}, clean_first=True)
    # First assign the preference to a remote, it has been cleared when exported locally
    client.run("install . --update")
    # *1 With revisions here is removing the package because it doesn't belong to the recipe

    assert "Hello0/1.0@lasote/stable from 'default' - Newer" in client.out
    failed_update_timestamps = timestamps()
    assert rebuild_timestamps == failed_update_timestamps

    # hack manifests, put old time
    for manifest_file in (recipe_manifest, package_manifest):
        manifest = load(manifest_file)
        lines = manifest.splitlines()
        lines[0] = "123"
        save(manifest_file, "\n".join(lines))

    client.run("install . --update")
    update_timestamps = timestamps()
    assert update_timestamps == initial_timestamps


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
    package_ids = client2.cache.package_layout(ref).package_ids()
    pref = PackageReference(ref, package_ids[0])
    package_path = client2.cache.package_layout(ref).package(pref)
    header = load(os.path.join(package_path, "header.h"))
    assert header == "//EMPTY!"


def test_upload_doesnt_follow_pref():
    servers = OrderedDict()
    servers['r1'] = TestServer()
    servers['r2'] = TestServer()
    client = TestClient(servers=servers, users={"r1": [("lasote", "mypass")],
                                                "r2": [("lasote", "mypass")]})
    ref = "Pkg/0.1@lasote/testing"
    pref = "%s:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9" % ref
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . Pkg/0.1@lasote/testing")
    client.run("upload Pkg/0.1@lasote/testing --all -r r2")
    client.run("remote list_pref Pkg/0.1@lasote/testing")

    assert "%s: r2" % pref in client.out
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


def test_remove_old_sources():
    # https://github.com/conan-io/conan/issues/1841
    test_server = TestServer()

    def upload(header_content):
        c = TestClient(servers={"default": test_server}, users={"default": [("lasote", "mypass")]})
        base = textwrap.dedent('''
            from conans import ConanFile
            class ConanLib(ConanFile):
                exports_sources = "*"
                def package(self):
                    self.copy("*")
            ''')
        c.save({"conanfile.py": base,
                "header.h": header_content})
        c.run("create . Pkg/0.1@lasote/channel")
        c.run("upload * --confirm --all")
        return c

    client = upload("mycontent1")
    time.sleep(1)
    upload("mycontent2")

    client.run("install Pkg/0.1@lasote/channel -u")

    if client.cache.config.revisions_enabled:
        # The binary package is not updated but downloaded, because the local one we have
        # belongs to a different revision and it is removed
        assert "Pkg/0.1@lasote/channel:%s - Download" % NO_SETTINGS_PACKAGE_ID in client.out
    else:
        assert "Pkg/0.1@lasote/channel:%s - Update" % NO_SETTINGS_PACKAGE_ID in client.out
    assert "Pkg/0.1@lasote/channel: Retrieving package %s" % NO_SETTINGS_PACKAGE_ID in client.out
    ref = ConanFileReference.loads("Pkg/0.1@lasote/channel")
    pref = PackageReference(ref, NO_SETTINGS_PACKAGE_ID)
    header = os.path.join(client.cache.package_layout(pref.ref).package(pref), "header.h")
    assert load(header) == "mycontent2"


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


def test_evil_insertions():
    ref = ConanFileReference.loads("lib1/1.0@conan/stable")
    ref2 = ConanFileReference.loads("lib2/1.0@conan/stable")

    client = TurboTestClient(servers={"default": TestServer()})
    pref1 = client.create(ref)
    client.upload_all(ref)

    client.create(ref2, conanfile=GenConanfile().with_requirement(ref))
    client.upload_all(ref2)

    client.run("remove {} -p {} -f".format(pref1.ref, pref1.id))

    # Even if we create the package folder artificially, the folder will be discarded and installed again.
    os.makedirs(os.path.join(client.cache_folder, "data", ref.dir_repr(), "package", pref1.id))

    client.run("install {}".format(ref2))

    assert "AssertionError: PREV" not in client.out
