import os

from conans.model.recipe_ref import RecipeReference
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.test_files import uncompress_packaged_files
from conan.test.utils.tools import TestClient


def test_reuse_uploaded_tgz():
    client = TestClient(default_server_user=True)
    # Download packages from a remote, then copy to another channel
    # and reupload them. Because they have not changed, the tgz is not created again

    # UPLOAD A PACKAGE
    ref = RecipeReference.loads("hello0/0.1@user/stable")
    files = {"conanfile.py": GenConanfile("hello0", "0.1").with_exports("*"),
             "another_export_file.lib": "to compress"}
    client.save(files)
    client.run("create . --user=user --channel=stable")
    client.run("upload %s -r default" % str(ref))
    assert "Compressing conan_export.tgz" in client.out
    assert "Compressing conan_package.tgz" in client.out


def test_reuse_downloaded_tgz():
    # Download packages from a remote, then copy to another channel
    # and reupload them. It needs to compress it again, not tgz is kept
    client = TestClient(default_server_user=True)
    # UPLOAD A PACKAGE
    files = {"conanfile.py": GenConanfile("hello0", "0.1").with_exports("*"),
             "another_export_file.lib": "to compress"}
    client.save(files)
    client.run("create . --user=user --channel=stable")
    client.run("upload hello0/0.1@user/stable -r default")
    assert "Compressing conan_export.tgz" in client.out
    assert "Compressing conan_package.tgz" in client.out

    # Other user downloads the package
    # THEN A NEW USER DOWNLOADS THE PACKAGES AND UPLOADS COMPRESSING AGAIN
    # BECAUSE ONLY TGZ IS KEPT WHEN UPLOADING
    other_client = TestClient(servers=client.servers, inputs=["admin", "password"])
    other_client.run("download hello0/0.1@user/stable -r default")
    other_client.run("upload hello0/0.1@user/stable -r default")
    assert "Compressing conan_export.tgz" in client.out
    assert "Compressing conan_package.tgz" in client.out


def test_upload_only_tgz_if_needed():
    client = TestClient(default_server_user=True)
    ref = RecipeReference.loads("hello0/0.1@user/stable")
    conanfile = GenConanfile("hello0", "0.1").with_exports("*").with_package_file("lib/file.lib",
                                                                                  "File")
    client.save({"conanfile.py": conanfile,
                 "file.txt": "contents"})
    client.run("create . --user=user --channel=stable")

    # Upload conans
    client.run("upload %s -r default --only-recipe" % str(ref))
    assert "Compressing conan_export.tgz" in client.out

    # Not needed to tgz again
    client.run("upload %s -r default --only-recipe" % str(ref))
    assert "Compressing" not in client.out

    # Check that conans exists on server
    server_paths = client.servers["default"].server_store
    conan_path = server_paths.conan_revisions_root(ref)
    assert os.path.exists(conan_path)

    latest_rrev = client.cache.get_latest_recipe_reference(ref)
    package_ids = client.cache.get_package_references(latest_rrev)
    pref = package_ids[0]

    # Upload package
    client.run("upload %s#*:%s -r default -c" % (str(ref), str(pref.package_id)))
    assert "Compressing conan_package.tgz" in client.out

    # Not needed to tgz again
    client.run("upload %s#*:%s -r default -c" % (str(ref), str(pref.package_id)))
    assert "Compressing" not in client.out

    # If we install the package again will be removed and re tgz
    client.run("install --requires=%s --build missing" % str(ref))
    # Upload package
    client.run("upload %s#*:%s -r default -c" % (str(ref), str(pref.package_id)))
    assert "Compressing" not in client.out

    # Check library on server
    folder = uncompress_packaged_files(server_paths, pref)
    libraries = os.listdir(os.path.join(folder, "lib"))
    assert len(libraries) == 1
