import json
import os
import platform
import stat
import unittest
from collections import OrderedDict

import pytest
import requests
from mock import patch
from requests import Response

from conans.errors import ConanException
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conan.internal.paths import EXPORT_SOURCES_TGZ_NAME, PACKAGE_TGZ_NAME
from conan.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, TestServer, \
    TurboTestClient, GenConanfile, TestRequester, TestingResponse
from conans.util.files import gzopen_without_timestamps, is_dirty, save, set_dirty

conanfile = """from conan import ConanFile
from conan.tools.files import copy
class MyPkg(ConanFile):
    name = "hello0"
    version = "1.2.1"
    exports_sources = "*"

    def package(self):
        copy(self, "*.cpp", self.source_folder, self.package_folder)
        copy(self, "*.h", self.source_folder, self.package_folder)
"""


class UploadTest(unittest.TestCase):

    @pytest.mark.artifactory_ready
    def test_upload_dirty(self):
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": GenConanfile("hello", "0.1")})
        client.run("create .")

        pkg_folder = client.created_layout().package()
        set_dirty(pkg_folder)

        client.run("upload * -r=default -c", assert_error=True)
        assert "ERROR: Package hello/0.1:da39a3ee5e6b4b0d3255bfef95601890afd80709 i" \
               "s corrupted, aborting upload." in client.out
        assert "Remove it with 'conan remove hello/0.1:da39a3ee5e6b4b0d3255bfef95601890afd80709" \
               in client.out

        # Test that removeing the binary allows moving forward
        client.run("remove hello/0.1:da39a3ee5e6b4b0d3255bfef95601890afd80709 -c")
        client.run("upload * -r=default --confirm")

    @pytest.mark.artifactory_ready
    def test_upload_force(self):
        ref = RecipeReference.loads("hello/0.1@conan/testing")
        client = TurboTestClient(default_server_user=True)
        pref = client.create(ref, conanfile=GenConanfile().with_package_file("myfile.sh", "foo"))
        client.run("upload * --confirm -r default")
        assert "Uploading package 'hello" in client.out
        client.run("upload * --confirm -r default")
        assert "Uploading package" not in client.out

        package_folder = client.get_latest_pkg_layout(pref).package()
        package_file_path = os.path.join(package_folder, "myfile.sh")

        if platform.system() == "Linux":
            client.run("remove '*' -c")
            client.create(ref, conanfile=GenConanfile().with_package_file("myfile.sh", "foo"))
            package_folder = client.get_latest_pkg_layout(pref).package()
            package_file_path = os.path.join(package_folder, "myfile.sh")
            os.system('chmod +x "{}"'.format(package_file_path))
            self.assertTrue(os.stat(package_file_path).st_mode & stat.S_IXUSR)
            client.run("upload * --confirm -r default")
            # Doesn't change revision, doesn't reupload
            self.assertNotIn("-> conan_package.tgz", client.out)
            self.assertIn("skipping upload", client.out)
            self.assertNotIn("Compressing package...", client.out)

        # with --force it really re-uploads it
        client.run("upload * --confirm --force -r default")
        assert "Uploading recipe 'hello" in client.out
        assert "Uploading package 'hello" in client.out

        if platform.system() == "Linux":
            client.run("remove '*' -c")
            client.run("install --requires={}".format(ref))
            package_folder = client.get_latest_pkg_layout(pref).package()
            package_file_path = os.path.join(package_folder, "myfile.sh")
            # Owner with execute permissions
            self.assertTrue(os.stat(package_file_path).st_mode & stat.S_IXUSR)

    @pytest.mark.artifactory_ready
    def test_pattern_upload(self):
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": conanfile})
        client.run("create . --user=user --channel=testing")
        client.run("upload hello0/*@user/testing --confirm -r default")
        assert "Uploading recipe 'hello0/1.2.1@" in client.out
        assert "Uploading package 'hello0/1.2.1@" in client.out

    def test_pattern_upload_no_recipes(self):
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": conanfile})
        client.run("upload bogus/*@dummy/testing --confirm -r default", assert_error=True)
        self.assertIn("No recipes found matching pattern 'bogus/*@dummy/testing'", client.out)

    def test_broken_sources_tgz(self):
        # https://github.com/conan-io/conan/issues/2854
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": conanfile,
                     "source.h": "my source"})
        client.run("create . --user=user --channel=testing")
        layout = client.exported_layout()

        def gzopen_patched(name, mode="r", fileobj=None, **kwargs):
            raise ConanException("Error gzopen %s" % name)
        with patch('conans.client.cmd.uploader.gzopen_without_timestamps', new=gzopen_patched):
            client.run("upload * --confirm -r default --only-recipe",
                       assert_error=True)
            self.assertIn("Error gzopen conan_sources.tgz", client.out)

            export_download_folder = layout.download_export()

            tgz = os.path.join(export_download_folder, EXPORT_SOURCES_TGZ_NAME)
            self.assertTrue(os.path.exists(tgz))
            self.assertTrue(is_dirty(tgz))

        client.run("upload * --confirm -r default --only-recipe")
        self.assertIn("Removing conan_sources.tgz, marked as dirty", client.out)
        self.assertTrue(os.path.exists(tgz))
        self.assertFalse(is_dirty(tgz))

    def test_broken_package_tgz(self):
        # https://github.com/conan-io/conan/issues/2854
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": conanfile,
                     "source.h": "my source"})
        client.run("create . --user=user --channel=testing")
        pref = client.get_latest_package_reference(RecipeReference.loads("hello0/1.2.1@user/testing"),
                                                   NO_SETTINGS_PACKAGE_ID)

        def gzopen_patched(name, mode="r", fileobj=None, **kwargs):
            if name == PACKAGE_TGZ_NAME:
                raise ConanException("Error gzopen %s" % name)
            return gzopen_without_timestamps(name, mode, fileobj, **kwargs)
        with patch('conans.client.cmd.uploader.gzopen_without_timestamps', new=gzopen_patched):
            client.run("upload * --confirm -r default", assert_error=True)
            self.assertIn("Error gzopen conan_package.tgz", client.out)

            download_folder = client.get_latest_pkg_layout(pref).download_package()
            tgz = os.path.join(download_folder, PACKAGE_TGZ_NAME)
            self.assertTrue(os.path.exists(tgz))
            self.assertTrue(is_dirty(tgz))

        client.run("upload * --confirm -r default")
        self.assertIn("WARN: Removing conan_package.tgz, marked as dirty", client.out)
        self.assertTrue(os.path.exists(tgz))
        self.assertFalse(is_dirty(tgz))

    def test_corrupt_upload(self):
        client = TestClient(default_server_user=True)

        client.save({"conanfile.py": conanfile,
                     "include/hello.h": ""})
        client.run("create . --user=frodo --channel=stable")
        package_folder = client.created_layout().package()
        save(os.path.join(package_folder, "added.txt"), "")
        os.remove(os.path.join(package_folder, "include/hello.h"))
        client.run("upload hello0/1.2.1@frodo/stable --check -r default", assert_error=True)
        self.assertIn("ERROR:     'include/hello.h'", client.out)
        self.assertIn("ERROR:     'added.txt'", client.out)
        self.assertIn("ERROR: There are corrupted artifacts, check the error logs", client.out)

    @pytest.mark.artifactory_ready
    def test_upload_modified_recipe(self):
        client = TestClient(default_server_user=True)

        client.save({"conanfile.py": conanfile,
                     "hello.cpp": "int i=0"})
        client.run("export . --user=frodo --channel=stable")
        rrev = client.exported_recipe_revision()
        client.run("upload hello0/1.2.1@frodo/stable -r default")
        assert "Uploading recipe 'hello0/1.2.1@frodo/stable#" in client.out

        client2 = TestClient(servers=client.servers, inputs=["admin", "password"])
        client2.save({"conanfile.py": conanfile + "\r\n#end",
                      "hello.cpp": "int i=1"})
        client2.run("export . --user=frodo --channel=stable")
        layout = client2.exported_layout()
        manifest, _ = layout.recipe_manifests()
        manifest.time += 10
        manifest.save(layout.export())
        client2.run("upload hello0/1.2.1@frodo/stable -r default")
        assert "Uploading recipe 'hello0/1.2.1@frodo/stable#" in client2.out

        # first client tries to upload again
        # The client tries to upload exactly the same revision already uploaded, so no changes
        client.run("upload hello0/1.2.1@frodo/stable -r default")
        self.assertIn(f"'hello0/1.2.1@frodo/stable#{rrev}' already "
                      "in server, skipping upload", client.out)

    @pytest.mark.artifactory_ready
    def test_upload_unmodified_recipe(self):
        client = TestClient(default_server_user=True)
        files = {"conanfile.py": GenConanfile("hello0", "1.2.1")}
        client.save(files)
        client.run("export . --user=frodo --channel=stable")
        rrev = client.exported_recipe_revision()
        client.run("upload hello0/1.2.1@frodo/stable -r default")
        assert "Uploading recipe 'hello0/1.2.1@frodo/stable#" in client.out

        client2 = TestClient(servers=client.servers, inputs=["admin", "password"])
        client2.save(files)
        client2.run("export . --user=frodo --channel=stable")
        layout = client2.exported_layout()
        manifest, _ = layout.recipe_manifests()
        manifest.time += 10
        manifest.save(layout.export())
        client2.run("upload hello0/1.2.1@frodo/stable -r default")
        self.assertIn(f"Recipe 'hello0/1.2.1@frodo/stable#761f54e34d59deb172d6078add7050a7' already "
                      "in server, skipping upload", client2.out)

        # first client tries to upload again
        client.run("upload hello0/1.2.1@frodo/stable -r default")
        self.assertIn(f"Recipe 'hello0/1.2.1@frodo/stable#{rrev}' "
                      "already in server, skipping upload", client.out)

    @pytest.mark.artifactory_ready
    def test_upload_unmodified_package(self):
        client = TestClient(default_server_user=True)

        client.save({"conanfile.py": conanfile,
                     "hello.cpp": ""})
        ref = RecipeReference.loads("hello0/1.2.1@frodo/stable")
        client.run("create . --user=frodo --channel=stable")
        client.run("upload hello0/1.2.1@frodo/stable -r default")

        client2 = TestClient(servers=client.servers, inputs=["admin", "password"])
        client2.save({"conanfile.py": conanfile,
                      "hello.cpp": ""})
        client2.run("create . --user=frodo --channel=stable")
        refs = client2.cache.get_latest_recipe_reference(ref)
        pkgs = client2.cache.get_package_references(refs)
        prev2 = client2.cache.get_latest_package_reference(pkgs[0])
        client2.run("upload hello0/1.2.1@frodo/stable -r default")
        self.assertIn(f"'{repr(prev2.ref)}' already "
                      "in server, skipping upload", client2.out)
        self.assertNotIn("Uploaded conan recipe 'hello0/1.2.1@frodo/stable' to 'default'",
                         client2.out)
        self.assertIn(f"'{prev2.repr_notime()}' already in server, skipping upload", client2.out)

        # first client tries to upload again
        refs = client.cache.get_latest_recipe_reference(ref)
        pkgs = client.cache.get_package_references(refs)
        prev1 = client.cache.get_latest_package_reference(pkgs[0])
        client.run("upload hello0/1.2.1@frodo/stable -r default")
        self.assertIn(f"'{repr(prev1.ref)}' already "
                      "in server, skipping upload", client.out)
        self.assertNotIn("Uploaded conan recipe 'hello0/1.2.1@frodo/stable' to 'default'",
                         client.out)
        self.assertIn(f"'{prev1.repr_notime()}' already in server, skipping upload", client2.out)

    def test_upload_no_overwrite_all(self):
        conanfile_new = GenConanfile("hello", "1.0").\
            with_import("from conan.tools.files import copy").\
            with_exports_sources(["*"]).\
            with_package('copy(self, "*", self.source_folder, self.package_folder)')

        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": conanfile_new,
                     "hello.h": ""})
        client.run("create . --user=frodo --channel=stable")
        # First time upload
        client.run("upload hello/1.0@frodo/stable -r default")
        self.assertNotIn("Forbidden overwrite", client.out)
        self.assertIn("Uploading recipe 'hello/1.0@frodo/stable", client.out)

        # CASE: Upload again
        client.run("upload hello/1.0@frodo/stable -r default")
        refs = client.cache.get_latest_recipe_reference(RecipeReference.loads("hello/1.0@frodo/stable"))
        pkgs = client.cache.get_package_references(refs)
        prev1 = client.cache.get_latest_package_reference(pkgs[0])
        self.assertIn(f"'{repr(prev1.ref)}' already "
                      "in server, skipping upload", client.out)
        self.assertIn(f"'{prev1.repr_notime()}' already in server, skipping upload", client.out)

    def test_skip_upload(self):
        """ Check that the option --skip does not upload anything
        """
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": GenConanfile("hello0", "1.2.1").with_exports("*"),
                     "file.txt": ""})
        client.run("create .")

        client.run("upload * --dry-run -r default -c")
        assert "Compressing" in client.out
        client.run("search * -r default")
        # after dry run nothing should be on the server
        assert "hello" not in client.out

        # now upload, the stuff should NOT be recompressed
        client.run("upload * -c -r default")
        # check if compressed files are re-used
        assert "Compressing" not in client.out
        # now it should be on the server
        client.run("search * -r default")
        assert "hello0/1.2.1" in client.out

    def test_upload_without_sources(self):
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . --name=pkg --version=0.1 --user=user --channel=testing")
        client.run("upload * --confirm -r default")
        client2 = TestClient(servers=client.servers, inputs=["admin", "password",
                                                             "lasote", "mypass"])

        client2.run("install --requires=pkg/0.1@user/testing")
        client2.run("remote remove default")
        server2 = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")],
                             users={"lasote": "mypass"})
        client2.servers = {"server2": server2}
        client2.update_servers()
        client2.run("upload * --confirm -r=server2")

        assert "Uploading recipe 'pkg" in client.out
        assert "Uploading package 'pkg" in client.out

    def test_upload_login_prompt_disabled_no_user(self):
        """ Without user info, uploads should fail when login prompt has been disabled.
        """
        files = {"conanfile.py": GenConanfile("hello0", "1.2.1")}
        client = TestClient(default_server_user=True)
        client.save(files)
        conan_conf = "core:non_interactive=True"
        client.save_home({"global.conf": conan_conf})

        client.run("create . --user=user --channel=testing")
        client.run("remote logout '*'")
        client.run("upload hello0/1.2.1@user/testing -r default", assert_error=True)

        self.assertIn("Conan interactive mode disabled", client.out)
        self.assertNotIn("-> conanmanifest.txt", client.out)
        self.assertNotIn("-> conanfile.py", client.out)
        self.assertNotIn("-> conan_export.tgz", client.out)

    def test_upload_login_prompt_disabled_user_not_authenticated(self):
        # When a user is not authenticated, uploads should fail when login prompt has been disabled.
        files = {"conanfile.py": GenConanfile("hello0", "1.2.1")}
        client = TestClient(default_server_user=True)
        client.save(files)
        conan_conf = "core:non_interactive=True"
        client.save_home({"global.conf": conan_conf})
        client.run("create . --user=user --channel=testing")
        client.run("remote logout '*'")
        client.run("remote set-user default lasote")
        client.run("upload hello0/1.2.1@user/testing -r default", assert_error=True)
        self.assertIn("Conan interactive mode disabled", client.out)
        self.assertNotIn("-> conanmanifest.txt", client.out)
        self.assertNotIn("-> conanfile.py", client.out)
        self.assertNotIn("-> conan_export.tgz", client.out)
        self.assertNotIn("Please enter a password for", client.out)

    def test_upload_login_prompt_disabled_user_authenticated(self):
        #  When user is authenticated, uploads should work even when login prompt has been disabled.
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": GenConanfile("hello0", "1.2.1")})
        conan_conf = "core:non_interactive=True"
        client.save_home({"global.conf": conan_conf})
        client.run("create . --user=user --channel=testing")
        client.run("remote logout '*'")
        client.run("remote login default admin -p password")
        client.run("upload hello0/1.2.1@user/testing -r default")

        assert "Uploading recipe 'hello0/1.2.1@" in client.out
        assert "Uploading package 'hello0/1.2.1@" in client.out

    def test_upload_key_error(self):
        files = {"conanfile.py": GenConanfile("hello0", "1.2.1")}
        server1 = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")], users={"lasote": "mypass"})
        server2 = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")], users={"lasote": "mypass"})
        servers = OrderedDict()
        servers["server1"] = server1
        servers["server2"] = server2
        client = TestClient(servers=servers)
        client.save(files)
        client.run("create . --user=user --channel=testing")
        client.run("remote login server1 lasote -p mypass")
        client.run("remote login server2 lasote -p mypass")
        client.run("upload hello0/1.2.1@user/testing -r server1")
        client.run("remove * --confirm")
        client.run("install --requires=hello0/1.2.1@user/testing -r server1")
        client.run("remote remove server1")
        client.run("upload hello0/1.2.1@user/testing -r server2")
        self.assertNotIn("ERROR: 'server1'", client.out)

    def test_concurrent_upload(self):
        # https://github.com/conan-io/conan/issues/4953
        server = TestServer()
        servers = OrderedDict([("default", server)])
        client = TurboTestClient(servers=servers, inputs=["admin", "password"])
        client2 = TurboTestClient(servers=servers, inputs=["admin", "password"])

        ref = RecipeReference.loads("lib/1.0@conan/testing")
        client.create(ref)
        rrev = client.exported_recipe_revision()
        client.upload_all(ref)
        # Upload same with client2
        client2.create(ref)
        client2.run("upload lib/1.0@conan/testing -r default")
        self.assertIn(f"'lib/1.0@conan/testing#{rrev}' already in "
                      "server, skipping upload", client2.out)
        self.assertNotIn("WARN", client2.out)

    def test_upload_without_user_channel(self):
        server = TestServer(users={"user": "password"}, write_permissions=[("*/*@*/*", "*")])
        servers = {"default": server}
        client = TestClient(servers=servers, inputs=["user", "password"])

        client.save({"conanfile.py": GenConanfile()})

        client.run('create . --name=lib --version=1.0')
        self.assertIn("lib/1.0: Package '{}' created".format(NO_SETTINGS_PACKAGE_ID), client.out)
        client.run('upload lib/1.0 -c -r default')
        assert "Uploading recipe 'lib/1.0" in client.out

        # Verify that in the remote it is stored as "_"
        pref = PkgReference.loads("lib/1.0@#0:{}#0".format(NO_SETTINGS_PACKAGE_ID))
        path = server.server_store.export(pref.ref)
        self.assertIn("/lib/1.0/_/_/0/export", path.replace("\\", "/"))

        path = server.server_store.package(pref)
        self.assertIn("/lib/1.0/_/_/0/package", path.replace("\\", "/"))

        # Should be possible with explicit package
        client.run(f'upload lib/1.0#*:{NO_SETTINGS_PACKAGE_ID} -c -r default --force')
        self.assertIn("Uploading artifacts", client.out)

    def test_upload_without_cleaned_user(self):
        """ When a user is not authenticated, uploads failed first time
        https://github.com/conan-io/conan/issues/5878
        """

        class EmptyCapabilitiesResponse(object):
            def __init__(self):
                self.ok = False
                self.headers = {"X-Conan-Server-Capabilities": "",
                                "Content-Type": "application/json"}
                self.status_code = 401
                self.content = b''

        class ErrorApiResponse(object):
            def __init__(self):
                self.ok = False
                self.status_code = 400
                self.content = "Unsupported Conan v1 repository request for 'conan'"

        class ServerCapabilitiesRequester(TestRequester):
            def __init__(self, *args, **kwargs):
                self._first_ping = True
                super(ServerCapabilitiesRequester, self).__init__(*args, **kwargs)

            def get(self, url, **kwargs):
                app, url = self._prepare_call(url, kwargs)
                if app:
                    if url.endswith("ping") and self._first_ping:
                        self._first_ping = False
                        return EmptyCapabilitiesResponse()
                    elif "hello0" in url and "1.2.1" in url and "v1" in url:
                        return ErrorApiResponse()
                    else:
                        response = app.get(url, **kwargs)
                        return TestingResponse(response)
                else:
                    return requests.get(url, **kwargs)

        server = TestServer(users={"user": "password"}, write_permissions=[("*/*@*/*", "*")])
        servers = {"default": server}
        client = TestClient(requester_class=ServerCapabilitiesRequester, servers=servers,
                            inputs=["user", "password"])
        files = {"conanfile.py": GenConanfile("hello0", "1.2.1")}
        client.save(files)
        client.run("create . --user=user --channel=testing")
        client.run("remote logout '*'")
        client.run("upload hello0/1.2.1@user/testing -r default")
        assert "Uploading recipe 'hello0/1.2.1@user/testing" in client.out

    def test_server_returns_200_ok(self):
        # https://github.com/conan-io/conan/issues/16104
        # If server returns 200 ok, without headers, it raises an error
        class MyHttpRequester(TestRequester):
            def get(self, _, **kwargs):
                resp = Response()
                resp.status_code = 200
                return resp

        client = TestClient(requester_class=MyHttpRequester, servers={"default": TestServer()})
        client.save({"conanfile.py": GenConanfile("hello0", "1.2.1")})
        client.run("create . ")
        client.run("upload * -c -r default", assert_error=True)
        assert "doesn't seem like a valid Conan remote" in client.out


def test_upload_only_without_user_channel():
    """
    check that we can upload only the packages without user and channel
    https://github.com/conan-io/conan/issues/10579
    """
    c = TestClient(default_server_user=True)

    c.save({"conanfile.py": GenConanfile("lib", "1.0")})
    c.run('create .')
    c.run("create . --user=user --channel=channel")
    c.run("list *")
    assert "lib/1.0@user/channel" in c.out

    c.run('upload */*@ -c -r=default')
    assert "Uploading recipe 'lib/1.0" in c.out  # FAILS!
    assert "lib/1.0@user/channel" not in c.out
    c.run("search * -r=default")
    assert "lib/1.0" in c.out
    assert "lib/1.0@user/channel" not in c.out

    c.run('upload */*@user/channel -c -r=default')
    assert "Uploading recipe 'lib/1.0@user/channel" in c.out
    c.run("search * -r=default")
    assert "lib/1.0@user/channel" in c.out
    assert "lib/1.0" in c.out


def test_upload_with_python_requires():
    # https://github.com/conan-io/conan/issues/14503
    c = TestClient(default_server_user=True)
    c.save({"tool/conanfile.py": GenConanfile("tool", "0.1"),
            "dep/conanfile.py": GenConanfile("dep", "0.1").with_python_requires("tool/[>=0.1]")})
    c.run("create tool")
    c.run("create dep")
    c.run("upload tool* -c -r=default")
    c.run("remove tool* -c")
    c.run("upload dep* -c -r=default")
    # This used to fail, but adding the enabled remotes to python_requires resolution, it works
    assert "tool/0.1: Downloaded recipe" in c.out


def test_upload_list_only_recipe():
    c = TestClient(default_server_user=True)
    c.save({"conanfile.py": GenConanfile("liba", "0.1")})
    c.run("create .")
    c.run("install --requires=liba/0.1 --format=json", redirect_stdout="graph.json")
    c.run("list --graph=graph.json --format=json", redirect_stdout="installed.json")
    c.run("upload --list=installed.json --only-recipe -r=default -c")
    assert "conan_package.tgz" not in c.out


def test_upload_json_output():
    c = TestClient(default_server_user=True)
    c.save({"conanfile.py": GenConanfile("liba", "0.1").with_settings("os")
                                                       .with_shared_option(False)})
    c.run("create . -s os=Linux")
    c.run("upload * -r=default -c --format=json")
    list_pkgs = json.loads(c.stdout)
    revs = list_pkgs["default"]["liba/0.1"]["revisions"]["a565bd5defd3a99e157698fcc6e23b25"]
    pkg = revs["packages"]["9e0f8140f0fe6b967392f8d5da9881e232e05ff8"]
    assert pkg["info"] == {"settings": {"os": "Linux"}, "options": {"shared": "False"}}
