import os
import textwrap
from collections import OrderedDict

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import (TestClient, TestServer, NO_SETTINGS_PACKAGE_ID, TurboTestClient,
                                     GenConanfile)
from conans.util.files import load


def test_download_recipe():
    client = TurboTestClient(default_server_user={"lasote": "pass"})
    # Test download of the recipe only
    conanfile = str(GenConanfile().with_name("pkg").with_version("0.1"))
    ref = ConanFileReference.loads("pkg/0.1@lasote/stable")

    client.create(ref, conanfile)
    client.upload_all(ref)
    client.remove_all()

    client.run("download pkg/0.1@lasote/stable --recipe")

    assert "Downloading conanfile.py" in client.out
    assert "Downloading conan_package.tgz" not in client.out
    ref_layout = client.cache.get_latest_ref_layout(ref)
    export_foder = ref_layout.export()
    assert os.path.exists(os.path.join(export_foder, "conanfile.py"))
    assert conanfile == load(os.path.join(export_foder, "conanfile.py"))
    assert not os.path.exists(os.path.join(ref_layout.base_folder, "package"))


def test_download_with_sources():
    server = TestServer()
    servers = OrderedDict()
    servers["default"] = server
    servers["other"] = TestServer()

    client = TestClient(servers=servers, users={"default": [("lasote", "mypass")],
                                                "other": [("lasote", "mypass")]})
    ref = ConanFileReference.loads("pkg/0.1@lasote/stable")
    conanfile = textwrap.dedent("""
    from conans import ConanFile

    class Pkg(ConanFile):
        name = "pkg"
        version = "0.1"
        exports_sources = "*"
    """)
    client.save({"conanfile.py": conanfile,
                 "file.h": "myfile.h",
                 "otherfile.cpp": "C++code"})
    client.run("export . lasote/stable")

    client.run(f"upload {ref}")
    client.run(f"remove {ref} -f")
    client.run(f"download {ref}")

    ref_layout = client.cache.get_latest_ref_layout(ref)
    source = ref_layout.export_sources()

    assert "Downloading conan_sources.tgz" in client.out
    assert "myfile.h" == load(os.path.join(source, "file.h"))
    assert "C++code" == load(os.path.join(source, "otherfile.cpp"))


def test_download_reference_without_packages():
    client = TestClient(default_server_user=True)
    client.save({"conanfile.py": GenConanfile().with_name("pkg").with_version("0.1")})
    ref = ConanFileReference.loads("pkg/0.1@user/stable")
    client.run("export . user/stable")
    client.run(f"upload {ref}")
    client.run(f"remove {ref} -f")
    client.run(f"download {ref}")

    # Check 'No remote binary packages found' warning
    assert "WARN: No remote binary packages found in remote" in client.out
    # Check at least conanfile.py is downloaded
    ref_layout = client.cache.get_latest_ref_layout(ref)
    assert os.path.exists(ref_layout.conanfile())


def test_download_reference_with_packages():
    server = TestServer()
    servers = {"default": server}

    client = TurboTestClient(servers=servers, users={"default": [("lasote", "mypass")]})
    ref = ConanFileReference.loads("pkg/0.1@lasote/stable")
    conanfile = textwrap.dedent("""
    from conans import ConanFile

    class Pkg(ConanFile):
        name = "pkg"
        version = "0.1"
        settings = "os"
    """)

    client.create(ref, conanfile)
    client.upload_all(ref)
    client.remove_all()

    client.run(f"download {ref}")

    pkg_layout = client.cache.get_latest_pkg_layout(ref=ref)
    ref_layout = client.cache.get_latest_ref_layout(ref=ref)

    # Check not 'No remote binary packages found' warning
    assert "WARN: No remote binary packages found in remote" not in client.out
    # Check at conanfile.py is downloaded
    assert os.path.exists(ref_layout.conanfile())
    # Check package folder created
    assert os.path.exists(pkg_layout.package())


def test_download_wrong_id():
    client = TurboTestClient(servers={"default": TestServer()},
                             users={"default": [("lasote", "mypass")]})
    ref = ConanFileReference.loads("pkg/0.1@lasote/stable")
    client.export(ref)
    client.upload_all(ref)
    client.remove_all()

    client.run(f"download {ref}:wrong", assert_error=True)
    assert "ERROR: Binary package not found: " \
           f"'{ref}#f3367e0e7d170aa12abccb175fee5f97:wrong'" in client.out


def test_download_pattern():
    client = TestClient()
    client.run("download pkg/*@user/channel", assert_error=True)
    assert "Provide a valid full reference without wildcards" in client.out


def test_download_full_reference():
    server = TestServer()
    servers = {"default": server}

    client = TurboTestClient(servers=servers, users={"default": [("lasote", "mypass")]})
    ref = ConanFileReference.loads("pkg/0.1@lasote/stable")

    client.create(ref)
    client.upload_all(ref)
    client.remove_all()

    client.run("download pkg/0.1@lasote/stable:{}".format(NO_SETTINGS_PACKAGE_ID))

    pkg_layout = client.cache.get_latest_pkg_layout(ref)
    ref_layout = client.cache.get_latest_ref_layout(ref)

    # Check not 'No remote binary packages found' warning
    assert "WARN: No remote binary packages found in remote" not in client.out
    # Check at conanfile.py is downloaded
    assert os.path.exists(ref_layout.conanfile())
    # Check package folder created
    assert os.path.exists(pkg_layout.package())


def test_download_with_full_reference_and_p():
    client = TestClient()
    client.run("download pkg/0.1@user/channel:{package_id} -p {package_id}".
               format(package_id="dupqipa4tog2ju3pncpnrzbim1fgd09g"),
               assert_error=True)
    assert "Use a full package reference (preferred) or the `--package` " \
           "command argument, but not both." in client.out


def test_download_with_package_and_recipe_args():
    client = TestClient()
    client.run("download eigen/3.3.4@conan/stable --recipe --package fake_id",
               assert_error=True)

    assert "ERROR: recipe parameter cannot be used together with package" in client.out


def test_download_package_argument():
    server = TestServer()
    servers = {"default": server}

    client = TurboTestClient(servers=servers, users={"default": [("lasote", "mypass")]})
    ref = ConanFileReference.loads("pkg/0.1@lasote/stable")

    client.create(ref)
    client.upload_all(ref)
    client.remove_all()

    client.run(f"download {ref} -p {NO_SETTINGS_PACKAGE_ID}")

    pkg_layout = client.cache.get_latest_pkg_layout(ref)
    ref_layout = client.cache.get_latest_ref_layout(ref)

    # Check not 'No remote binary packages found' warning
    assert "WARN: No remote binary packages found in remote" not in client.out
    # Check at conanfile.py is downloaded
    assert os.path.exists(ref_layout.conanfile())
    # Check package folder created
    assert os.path.exists(pkg_layout.package())


def test_download_not_found_reference():
    server = TestServer()
    servers = {"default": server}
    client = TurboTestClient(servers=servers, users={"default": [("lasote", "mypass")]})
    ref = ConanFileReference.loads("pkg/0.1@lasote/stable")
    client.run(f"download {ref}", assert_error=True)
    assert f"ERROR: Recipe not found: '{ref}'" in client.out


def test_no_user_channel():
    # https://github.com/conan-io/conan/issues/6009
    server = TestServer(users={"user": "password"}, write_permissions=[("*/*@*/*", "*")])
    client = TestClient(servers={"default": server}, users={"default": [("user", "password")]})
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . pkg/1.0@")
    client.run("upload * --all --confirm")
    client.run("remove * -f")

    client.run("download pkg/1.0:{}".format(NO_SETTINGS_PACKAGE_ID))
    assert "pkg/1.0: Downloading pkg/1.0:%s" % NO_SETTINGS_PACKAGE_ID in client.out
    assert "pkg/1.0: Package installed %s" % NO_SETTINGS_PACKAGE_ID in client.out

    # All
    client.run("remove * -f")
    client.run("download pkg/1.0@")
    assert "pkg/1.0: Downloading pkg/1.0:%s" % NO_SETTINGS_PACKAGE_ID in client.out
    assert "pkg/1.0: Package installed %s" % NO_SETTINGS_PACKAGE_ID in client.out
