import os

from conans.model.ref import ConanFileReference, PackageReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.test_files import uncompress_packaged_files
from conans.test.utils.tools import TestClient


def test_reuse_uploaded_tgz():
    client = TestClient(default_server_user=True)
    # Download packages from a remote, then copy to another channel
    # and reupload them. Because they have not changed, the tgz is not created again

    # UPLOAD A PACKAGE
    ref = ConanFileReference.loads("Hello0/0.1@user/stable")
    files = {"conanfile.py": GenConanfile("Hello0", "0.1").with_exports("*"),
             "another_export_file.lib": "to compress"}
    client.save(files)
    client.run("create . user/stable")
    client.run("upload %s --all" % str(ref))
    assert "Compressing recipe" in client.out
    assert "Compressing package" in client.out

    # UPLOAD TO A DIFFERENT CHANNEL WITHOUT COMPRESS AGAIN
    client.run("copy %s user/testing --all" % str(ref))
    client.run("upload Hello0/0.1@user/testing --all")
    assert "Compressing recipe" not in client.out
    assert "Compressing package" not in client.out


def test_reuse_downloaded_tgz():
    # Download packages from a remote, then copy to another channel
    # and reupload them. It needs to compress it again, not tgz is kept
    client = TestClient(default_server_user=True)
    # UPLOAD A PACKAGE
    files = {"conanfile.py": GenConanfile("Hello0", "0.1").with_exports("*"),
             "another_export_file.lib": "to compress"}
    client.save(files)
    client.run("create . user/stable")
    client.run("upload Hello0/0.1@user/stable --all")
    assert "Compressing recipe" in client.out
    assert "Compressing package" in client.out

    # Other user downloads the package
    # THEN A NEW USER DOWNLOADS THE PACKAGES AND UPLOADS COMPRESSING AGAIN
    # BECAUSE ONLY TGZ IS KEPT WHEN UPLOADING
    other_client = TestClient(servers=client.servers, users={"default": [("user", "password")]})
    other_client.run("download Hello0/0.1@user/stable")
    other_client.run("upload Hello0/0.1@user/stable --all")
    assert "Compressing recipe" in client.out
    assert "Compressing package" in client.out


def test_upload_only_tgz_if_needed():
    client = TestClient(default_server_user=True)
    ref = ConanFileReference.loads("Hello0/0.1@user/stable")
    conanfile = GenConanfile("Hello0", "0.1").with_exports("*").with_package_file("lib/file.lib",
                                                                                  "File")
    client.save({"conanfile.py": conanfile,
                 "file.txt": "contents"})
    client.run("create . user/stable")

    # Upload conans
    client.run("upload %s" % str(ref))
    assert "Compressing recipe" in client.out

    # Not needed to tgz again
    client.run("upload %s" % str(ref))
    assert "Compressing recipe" not in client.out

    # Check that conans exists on server
    server_paths = client.servers["default"].server_store
    conan_path = server_paths.conan_revisions_root(ref)
    assert os.path.exists(conan_path)
    package_ids = client.cache.package_layout(ref).package_ids()
    pref = PackageReference(ref, package_ids[0])

    # Upload package
    client.run("upload %s -p %s" % (str(ref), str(package_ids[0])))
    assert "Compressing package" in client.out

    # Not needed to tgz again
    client.run("upload %s -p %s" % (str(ref), str(package_ids[0])))
    assert "Compressing package" not in client.out

    # If we install the package again will be removed and re tgz
    client.run("install %s --build missing" % str(ref))
    # Upload package
    client.run("upload %s -p %s" % (str(ref), str(package_ids[0])))
    assert "Compressing package" not in client.out

    # Check library on server
    folder = uncompress_packaged_files(server_paths, pref)
    libraries = os.listdir(os.path.join(folder, "lib"))
    assert len(libraries) == 1
