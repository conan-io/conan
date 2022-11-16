import os

import pytest

from conans.model.recipe_ref import RecipeReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient
from conans.util.files import load


@pytest.fixture(scope="module")
def setup():
    client = TestClient(default_server_user=True)
    conanfile = GenConanfile().with_settings("os", "arch").with_package_file("hellohello0.h", "x")
    client.save({"conanfile.py": conanfile})
    ref = RecipeReference.loads("hello0/0.1@lasote/stable")
    client.run("export . --name=hello0 --version=0.1 --user=lasote --channel=stable")
    client.run("install --requires={} -s os=Windows --build missing".format(ref))
    client.run("install --requires={} -s os=Linux --build missing".format(ref))
    client.run("install --requires={} -s os=Linux -s arch=x86 --build missing".format(ref))
    client.run("upload {} -r default".format(ref))
    latest_rrev = client.cache.get_latest_recipe_reference(ref)
    packages = client.cache.get_package_references(latest_rrev)
    package_ids = [package.package_id for package in packages]
    return client, ref, package_ids, str(conanfile)


def test_download_all(setup):
    client, ref, package_ids, _ = setup
    new_client = TestClient(servers=client.servers, inputs=["admin", "password"])
    # Should retrieve the three packages
    new_client.run("download hello0/0.1@lasote/stable:* -r default")
    latest_rrev = new_client.cache.get_latest_recipe_reference(ref)
    packages = new_client.cache.get_package_references(latest_rrev)
    new_package_ids = [package.package_id for package in packages]
    assert set(new_package_ids) == set(package_ids)


def test_download_some_reference(setup):
    client, ref, package_ids, _ = setup
    new_client = TestClient(servers=client.servers, inputs=["admin", "password"])
    # Should retrieve the specified packages
    new_client.run("download hello0/0.1@lasote/stable:%s -r default" % package_ids[0])
    assert len(package_ids) == 3

    # try to re-download the package we have just installed, will skip download
    latest_prev = new_client.get_latest_package_reference("hello0/0.1@lasote/stable")
    new_client.run(f"download {latest_prev.repr_notime()} -r default")
    assert f"Skip {latest_prev.repr_notime()} download, already in cache" in new_client.out


def test_download_recipe_twice(setup):
    client, ref, package_ids, conanfile = setup
    new_client = TestClient(servers=client.servers, inputs=["admin", "password"])
    new_client.run("download hello0/0.1@lasote/stable -r default")
    ref = RecipeReference.loads("hello0/0.1@lasote/stable")

    conanfile_path = new_client.get_latest_ref_layout(ref).conanfile()
    assert conanfile == load(conanfile_path)

    new_client.run("download hello0/0.1@lasote/stable -r default")
    assert conanfile == load(conanfile_path)

    new_client.run("download hello0/0.1@lasote/stable -r default")
    assert conanfile == load(conanfile_path)


def test_download_packages_twice(setup):
    client, ref, package_ids, _ = setup
    new_client = TestClient(servers=client.servers, inputs=["admin", "password"])
    expected_header_contents = "x"

    new_client.run("download hello0/0.1@lasote/stable:* -r default")
    pref = client.get_latest_package_reference("hello0/0.1@lasote/stable", package_id=package_ids[0])
    package_folder = new_client.get_latest_pkg_layout(pref).package()
    got_header = load(os.path.join(package_folder, "hellohello0.h"))
    assert expected_header_contents == got_header

    new_client.run("download hello0/0.1@lasote/stable:* -r default")
    got_header = load(os.path.join(package_folder, "hellohello0.h"))
    assert expected_header_contents == got_header

    new_client.run("download hello0/0.1@lasote/stable:* -r default")
    got_header = load(os.path.join(package_folder, "hellohello0.h"))
    assert expected_header_contents == got_header


def test_download_all_but_no_packages():
    # Remove all from remote
    new_client = TestClient(default_server_user=True)

    # Try to install all
    new_client.run("download hello0/0.1@lasote/stable:* -r default", assert_error=True)
    assert "Recipe not found: 'hello0/0.1@lasote/stable'" in new_client.out

    # Upload the recipe (we don't have packages)
    new_client.save({"conanfile.py": GenConanfile()})
    new_client.run("export . --name=hello0 --version=0.1 --user=lasote --channel=stable")
    new_client.run("upload hello0/0.1@lasote/stable -r default")

    # And try to download all
    new_client.run("download hello0/0.1@lasote/stable:* -r default", assert_error=True)
    assert "There are no packages matching 'hello0/0.1@lasote/stable:*'" in new_client.out
