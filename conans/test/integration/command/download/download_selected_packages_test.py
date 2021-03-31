import os

import pytest

from conans.model.ref import ConanFileReference, PackageReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient
from conans.util.files import load


@pytest.fixture(scope="module")
def setup():
    client = TestClient(default_server_user=True)
    conanfile = GenConanfile().with_settings("os", "arch").with_package_file("helloHello0.h", "x")
    client.save({"conanfile.py": conanfile})
    ref = ConanFileReference.loads("Hello0/0.1@lasote/stable")
    client.run("export . {}".format(ref))
    client.run("install {} -s os=Windows --build missing".format(ref))
    client.run("install {} -s os=Linux --build missing".format(ref))
    client.run("install {} -s os=Linux -s arch=x86 --build missing".format(ref))
    client.run("upload {} --all".format(ref))

    package_ids = os.listdir(client.cache.package_layout(ref).packages())
    return client, ref, package_ids, str(conanfile)


def test_download_all(setup):
    client, ref, package_ids, _ = setup
    new_client = TestClient(servers=client.servers, users=client.users)
    # Should retrieve the three packages
    new_client.run("download Hello0/0.1@lasote/stable")
    packages = os.listdir(os.path.join(new_client.cache.package_layout(ref).packages()))
    assert set(packages) == set(package_ids)


def test_download_some_reference(setup):
    client, ref, package_ids, _ = setup
    new_client = TestClient(servers=client.servers, users=client.users)
    # Should retrieve the specified packages
    new_client.run("download Hello0/0.1@lasote/stable -p %s" % package_ids[0])
    packages = os.listdir(new_client.cache.package_layout(ref).packages())
    assert len(packages) == 1
    assert packages[0] in package_ids

    new_client.run("download Hello0/0.1@lasote/stable -p %s -p %s" % (package_ids[0],
                                                                      package_ids[1]))
    packages = os.listdir(new_client.cache.package_layout(ref).packages())
    assert len(packages) == 2
    assert packages[0] in package_ids
    assert packages[1] in package_ids


def test_download_recipe_twice(setup):
    client, ref, package_ids, conanfile = setup
    new_client = TestClient(servers=client.servers, users=client.users)
    new_client.run("download Hello0/0.1@lasote/stable")
    conanfile_path = new_client.cache.package_layout(ref).conanfile()
    assert conanfile == load(conanfile_path)

    new_client.run("download Hello0/0.1@lasote/stable")
    assert conanfile == load(conanfile_path)

    new_client.run("download Hello0/0.1@lasote/stable")
    assert conanfile == load(conanfile_path)


def test_download_packages_twice(setup):
    client, ref, package_ids, _ = setup
    new_client = TestClient(servers=client.servers, users=client.users)
    expected_header_contents = "x"
    pref = PackageReference(ref, package_ids[0])
    package_folder = new_client.cache.package_layout(ref).package(pref)

    new_client.run("download Hello0/0.1@lasote/stable")
    got_header = load(os.path.join(package_folder, "helloHello0.h"))
    assert expected_header_contents == got_header

    new_client.run("download Hello0/0.1@lasote/stable")
    got_header = load(os.path.join(package_folder, "helloHello0.h"))
    assert expected_header_contents == got_header

    new_client.run("download Hello0/0.1@lasote/stable")
    got_header = load(os.path.join(package_folder, "helloHello0.h"))
    assert expected_header_contents == got_header


def test_download_all_but_no_packages():
    # Remove all from remote
    new_client = TestClient(default_server_user=True)

    # Try to install all
    new_client.run("download Hello0/0.1@lasote/stable", assert_error=True)
    assert "Recipe not found: 'Hello0/0.1@lasote/stable'" in new_client.out

    # Upload only the recipe
    new_client.save({"conanfile.py": GenConanfile()})
    new_client.run("export . Hello0/0.1@lasote/stable ")
    new_client.run("upload  Hello0/0.1@lasote/stable --all")

    # And try to download all
    new_client.run("download Hello0/0.1@lasote/stable")
    assert "No remote binary packages found in remote" in new_client.out
