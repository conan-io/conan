import os
import textwrap
import time
from collections import OrderedDict
from time import sleep

import pytest
from mock import patch

from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import CONAN_MANIFEST
from conans.server.revision_list import RevisionList
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
    client.run("upload Pkg/0.1@lasote/testing --all -r default")

    client2 = TestClient(servers=client.servers, users=client.users)
    client2.run("install Pkg/0.1@lasote/testing")
    value = load(os.path.join(client2.current_folder, "file.txt"))

    time.sleep(1)  # Make sure the new timestamp is later
    client.run("create . Pkg/0.1@lasote/testing")
    client.run("upload Pkg/0.1@lasote/testing --all -r default")

    client2.run("install Pkg/0.1@lasote/testing")
    new_value = load(os.path.join(client2.current_folder, "file.txt"))
    assert value == new_value

    client2.run("install Pkg/0.1@lasote/testing --update")
    assert "Current package revision is older than the remote one" in client2.out
    new_value = load(os.path.join(client2.current_folder, "file.txt"))
    assert value != new_value

    # Now check newer local modifications are not overwritten
    time.sleep(1)  # Make sure the new timestamp is later
    client.run("create . Pkg/0.1@lasote/testing")
    client.run("upload Pkg/0.1@lasote/testing --all -r default")

    client2.save({"conanfile.py": conanfile})
    client2.run("create . Pkg/0.1@lasote/testing")
    client2.run("install Pkg/0.1@lasote/testing")
    value2 = load(os.path.join(client2.current_folder, "file.txt"))
    client2.run("install Pkg/0.1@lasote/testing --update -r default")
    assert "Current package revision is newer than the remote one" in client2.out
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
    client.run("upload Hello0/1.0@lasote/stable --all -r default")

    prev = client.get_latest_prev("Hello0/1.0@lasote/stable")

    ref = ConanFileReference.loads("Hello0/1.0@lasote/stable")

    initial_recipe_timestamp = client.cache.get_timestamp(client.cache.get_latest_rrev(ref))
    initial_package_timestamp = client.cache.get_timestamp(prev)

    time.sleep(1)

    # Change and rebuild package
    client.save({"conanfile.py": GenConanfile("Hello0", "1.0").with_test("pass")}, clean_first=True)
    client.run("export . lasote/stable")
    client.run("install Hello0/1.0@lasote/stable --build")

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
    client.run("upload Hello0/1.0@lasote/stable --all -r default")

    client2 = TestClient(servers=client.servers, users=client.users)
    client2.run("install Hello0/1.0@lasote/stable")

    assert str(client2.out).count("Downloading conaninfo.txt") == 1

    client.save({"header.h": "//EMPTY!"})
    sleep(1)
    client.run("export . lasote/stable")
    client.run("install Hello0/1.0@lasote/stable --build")
    client.run("upload Hello0/1.0@lasote/stable --all -r default")

    client2.run("install Hello0/1.0@lasote/stable --update")
    ref = ConanFileReference.loads("Hello0/1.0@lasote/stable")
    pref = client.get_latest_prev(ref)
    package_path = client2.get_latest_pkg_layout(pref).package()
    header = load(os.path.join(package_path, "header.h"))
    assert header == "//EMPTY!"


def test_update_binaries_failed():
    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . Pkg/0.1@lasote/testing")
    client.run("install Pkg/0.1@lasote/testing --update")
    assert "Pkg/0.1@lasote/testing: WARN: Can't update, there are no remotes configured or enabled" in client.out
