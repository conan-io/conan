import itertools
import os
import platform
import re
import stat
import textwrap
import unittest
from collections import OrderedDict, defaultdict
from copy import copy

import pytest
import requests
from mock import patch

from conans import REVISIONS
from conans.errors import ConanException
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.paths import EXPORT_SOURCES_TGZ_NAME, PACKAGE_TGZ_NAME
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, TestServer, \
    TurboTestClient, GenConanfile, TestRequester, TestingResponse
from conans.util.env import environment_update
from conans.util.files import gzopen_without_timestamps, is_dirty, save, set_dirty

conanfile = """from conan import ConanFile
from conan.tools.files import copy
class MyPkg(ConanFile):
    name = "hello0"
    version = "1.2.1"
    exports_sources = "*"

    def package(self):
        copy(self, "*", self.source_folder, self.package_folder)
"""


class UploadTest(unittest.TestCase):

    @pytest.mark.xfail(reason="cache2.0 will remove -p make sense for 2.0?")
    def test_upload_dirty(self):
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": GenConanfile("hello", "0.1")})
        client.run("create . --user=lasote --channel=testing")
        ref = RecipeReference.loads("hello/0.1@lasote/testing")

        rrev = client.cache.get_latest_recipe_reference(ref)
        prev = client.cache.get_latest_package_reference(rrev)
        pkg_folder = client.cache.pkg_layout(prev).package()
        set_dirty(pkg_folder)

        client.run("upload * --confirm", assert_error=True)
        self.assertIn(f"ERROR: hello/0.1@lasote/testing:{NO_SETTINGS_PACKAGE_ID}: "
                      "Upload package to 'default' failed: Package %s is corrupted, aborting upload"
                      % str(prev), client.out)
        self.assertIn("Remove it with 'conan remove hello/0.1@lasote/testing -p=%s'"
                      % NO_SETTINGS_PACKAGE_ID, client.out)

        # TODO: cache2.0 check if this makes sense for 2.0, xfail test for the moment
        client.run("remove hello/0.1@lasote/testing -p=%s -f" % NO_SETTINGS_PACKAGE_ID)
        client.run("upload * --confirm")

    @pytest.mark.artifactory_ready
    def test_upload_force(self):
        ref = RecipeReference.loads("hello/0.1@conan/testing")
        client = TurboTestClient(default_server_user=True)
        pref = client.create(ref, conanfile=GenConanfile().with_package_file("myfile.sh", "foo"))
        client.run("upload * --confirm -r default")
        self.assertIn("Uploading conan_package.tgz", client.out)
        client.run("upload * --confirm -r default")
        self.assertNotIn("Uploading conan_package.tgz", client.out)

        package_folder = client.get_latest_pkg_layout(pref).package()
        package_file_path = os.path.join(package_folder, "myfile.sh")

        if platform.system() == "Linux":
            client.run("remove '*' -f")
            client.create(ref, conanfile=GenConanfile().with_package_file("myfile.sh", "foo"),
                          args="--build=*")
            os.system('chmod +x "{}"'.format(package_file_path))
            self.assertTrue(os.stat(package_file_path).st_mode & stat.S_IXUSR)
            client.run("upload * --confirm -r default")
            # Doesn't change revision, doesn't reupload
            self.assertNotIn("Uploading conan_package.tgz", client.out)
            self.assertIn("skipping upload", client.out)
            self.assertNotIn("Compressing package...", client.out)

        # with --force it really re-uploads it
        client.run("upload * --confirm --force -r default")
        self.assertIn("Uploading conanfile.py", client.out)
        self.assertIn("Uploading conan_package.tgz", client.out)

        if platform.system() == "Linux":
            client.run("remove '*' -f")
            client.run("install --requires={}".format(ref))
            # Owner with execute permissions
            self.assertTrue(os.stat(package_file_path).st_mode & stat.S_IXUSR)

    def test_upload_binary_not_existing(self):
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": GenConanfile()})
        client.run("export . --name=hello --version=0.1 --user=lasote --channel=testing")
        client.run("upload hello/0.1@lasote/testing#latest:123 -r default "
                   "--only-recipe", assert_error=True)
        self.assertIn("There are no packages matching hello/0.1@lasote/testing#latest:123",
                      client.out)

    def test_not_existing_error(self):
        """ Trying to upload with pattern not matched must raise an Error
        """
        client = TestClient(default_server_user=True)
        client.run("upload some_nonsense* -r default --only-recipe", assert_error=True)
        self.assertIn("No recipes found matching pattern 'some_nonsense*'", client.out)

    def test_non_existing_recipe_error(self):
        """ Trying to upload a non-existing recipe must raise an Error
        """
        client = TestClient(default_server_user=True)
        client.run("upload pkg/0.1@user/channel -r default --only-recipe", assert_error=True)
        self.assertIn("No recipes found matching pattern 'pkg/0.1@user/channel'", client.out)

    def test_non_existing_package_error(self):
        """ Trying to upload a non-existing package must raise an Error
        """
        client = TestClient(default_server_user=True)
        client.run("upload pkg/0.1@user/channel -r default --only-recipe", assert_error=True)
        self.assertIn("No recipes found matching pattern 'pkg/0.1@user/channel'", client.out)

    def test_upload_with_pref(self):
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": conanfile})
        client.run("create . --user=user --channel=testing")
        client.run("upload hello0/1.2.1@user/testing#*:{} -c "
                   "-r default --only-recipe".format(NO_SETTINGS_PACKAGE_ID))
        self.assertIn("Uploading hello0/1.2.1@user/testing#5dc5:da39#eb26", client.out)

    def test_pattern_upload(self):
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": conanfile})
        client.run("create . --user=user --channel=testing")
        client.run("upload hello0/*@user/testing --confirm -r default")
        self.assertIn("Uploading conanmanifest.txt", client.out)
        self.assertIn("Uploading conan_package.tgz", client.out)
        self.assertIn("Uploading conanfile.py", client.out)

    @pytest.mark.xfail(reason="cache2.0 query not yet implemented")
    def test_query_upload(self):
        client = TestClient(default_server_user=True)
        conanfile_upload_query = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.files import copy
            class MyPkg(ConanFile):
                name = "hello1"
                version = "1.2.1"
                exports_sources = "*"
                settings = "os", "arch"

                def package(self):
                    copy(self, "*", self.source_folder, self.package_folder)
            """)
        client.save({"conanfile.py": conanfile_upload_query})

        for _os, arch in itertools.product(["Macos", "Linux", "Windows"],
                                           ["armv8", "x86_64"]):
            client.run("create . --user=user --channel=testing -s os=%s -s arch=%s" % (_os, arch))

        # Check that the right number of packages are picked up by the queries
        client.run("upload hello1/*@user/testing --confirm -q 'os=Windows or os=Macos' -r default")
        for i in range(1, 5):
            self.assertIn("Uploading package %d/4" % i, client.out)
        self.assertNotIn("already in server, skipping upload", client.out)

        client.run("upload hello1/*@user/testing --confirm -q 'os=Linux and arch=x86_64' -r default")
        self.assertIn("Uploading package 1/1", client.out)

        client.run("upload hello1/*@user/testing --confirm -q 'arch=armv8' -r default")
        for i in range(1, 4):
            self.assertIn("Uploading package %d/3" % i, client.out)
        self.assertIn("already in server, skipping upload", client.out)

        # Check that a query not matching any packages doesn't upload any packages
        client.run("upload hello1/*@user/testing --confirm -q 'arch=sparc' -r default")
        self.assertNotIn("Uploading package", client.out)

        # Check that an invalid query fails
        client.run("upload hello1/*@user/testing --confirm -q 'blah blah blah' -r default", assert_error=True)
        self.assertIn("Invalid package query", client.out)

    def test_broken_sources_tgz(self):
        # https://github.com/conan-io/conan/issues/2854
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": conanfile,
                     "source.h": "my source"})
        client.run("create . --user=user --channel=testing")
        ref = RecipeReference.loads("hello0/1.2.1@user/testing")

        def gzopen_patched(name, mode="r", fileobj=None, **kwargs):
            raise ConanException("Error gzopen %s" % name)
        with patch('conans.client.cmd.uploader.gzopen_without_timestamps', new=gzopen_patched):
            client.run("upload * --confirm -r default --only-recipe",
                       assert_error=True)
            self.assertIn("Error gzopen conan_sources.tgz", client.out)

            latest_rrev = client.cache.get_latest_recipe_reference(ref)
            export_download_folder = client.cache.ref_layout(latest_rrev).download_export()

            tgz = os.path.join(export_download_folder, EXPORT_SOURCES_TGZ_NAME)
            self.assertTrue(os.path.exists(tgz))
            self.assertTrue(is_dirty(tgz))

        client.run("upload * --confirm -r default --only-recipe")
        self.assertIn("WARN: hello0/1.2.1@user/testing: Removing conan_sources.tgz, "
                      "marked as dirty", client.out)
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
        self.assertIn("WARN: hello0/1.2.1@user/testing:%s: "
                      "Removing conan_package.tgz, marked as dirty" % NO_SETTINGS_PACKAGE_ID,
                      client.out)
        self.assertTrue(os.path.exists(tgz))
        self.assertFalse(is_dirty(tgz))

    def test_corrupt_upload(self):
        client = TestClient(default_server_user=True)

        client.save({"conanfile.py": conanfile,
                     "include/hello.h": ""})
        client.run("create . --user=frodo --channel=stable")
        ref = RecipeReference.loads("hello0/1.2.1@frodo/stable")
        latest_rrev = client.cache.get_latest_recipe_reference(ref)
        pkg_ids = client.cache.get_package_references(latest_rrev)
        latest_prev = client.cache.get_latest_package_reference(pkg_ids[0])
        package_folder = client.cache.pkg_layout(latest_prev).package()
        save(os.path.join(package_folder, "added.txt"), "")
        os.remove(os.path.join(package_folder, "include/hello.h"))
        client.run("upload hello0/1.2.1@frodo/stable --check -r default", assert_error=True)
        self.assertIn("ERROR:     'include/hello.h'", client.out)
        self.assertIn("ERROR:     'added.txt'", client.out)
        self.assertIn("ERROR: There are corrupted artifacts, check the error logs", client.out)

    def test_upload_modified_recipe(self):
        client = TestClient(default_server_user=True)

        client.save({"conanfile.py": conanfile,
                     "hello.cpp": "int i=0"})
        client.run("export . --user=frodo --channel=stable")
        rrev = client.exported_recipe_revision()
        client.run("upload hello0/1.2.1@frodo/stable -r default")
        self.assertIn("Uploading conanmanifest.txt", client.out)
        assert "Uploading hello0/1.2.1@frodo/stable" in client.out

        client2 = TestClient(servers=client.servers, inputs=["admin", "password"])
        client2.save({"conanfile.py": conanfile + "\r\n#end",
                      "hello.cpp": "int i=1"})
        client2.run("export . --user=frodo --channel=stable")
        ref = RecipeReference.loads("hello0/1.2.1@frodo/stable")
        latest_rrev = client2.cache.get_latest_recipe_reference(ref)
        manifest, _ = client2.cache.ref_layout(latest_rrev).recipe_manifests()
        manifest.time += 10
        manifest.save(client2.cache.ref_layout(latest_rrev).export())
        client2.run("upload hello0/1.2.1@frodo/stable -r default")
        self.assertIn("Uploading conanmanifest.txt", client2.out)
        assert "Uploading hello0/1.2.1@frodo/stable" in client2.out

        # first client tries to upload again
        # The client tries to upload exactly the same revision already uploaded, so no changes
        client.run("upload hello0/1.2.1@frodo/stable -r default")
        self.assertIn(f"hello0/1.2.1@frodo/stable#{rrev} already "
                      "in server, skipping upload", client.out)

    def test_upload_unmodified_recipe(self):
        client = TestClient(default_server_user=True)
        files = {"conanfile.py": GenConanfile("hello0", "1.2.1")}
        client.save(files)
        client.run("export . --user=frodo --channel=stable")
        rrev = client.exported_recipe_revision()
        client.run("upload hello0/1.2.1@frodo/stable -r default")
        self.assertIn("Uploading conanmanifest.txt", client.out)
        assert "Uploading hello0/1.2.1@frodo/stable" in client.out

        client2 = TestClient(servers=client.servers, inputs=["admin", "password"])
        client2.save(files)
        client2.run("export . --user=frodo --channel=stable")
        ref = RecipeReference.loads("hello0/1.2.1@frodo/stable")
        rrev2 = client2.cache.get_latest_recipe_reference(ref)
        manifest, _ = client2.cache.ref_layout(rrev2).recipe_manifests()
        manifest.time += 10
        manifest.save(client2.cache.ref_layout(rrev2).export())
        client2.run("upload hello0/1.2.1@frodo/stable -r default")
        self.assertNotIn("Uploading conanmanifest.txt", client2.out)
        self.assertIn(f"hello0/1.2.1@frodo/stable#761f54e34d59deb172d6078add7050a7 already "
                      "in server, skipping upload", client2.out)

        # first client tries to upload again
        client.run("upload hello0/1.2.1@frodo/stable -r default")
        self.assertNotIn("Uploading conanmanifest.txt", client.out)
        self.assertIn(f"hello0/1.2.1@frodo/stable#{rrev} "
                      "already in server, skipping upload", client.out)

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
        self.assertIn(f"{repr(prev2.ref)} already "
                      "in server, skipping upload", client2.out)
        self.assertNotIn("Uploading conanfile.py", client2.out)
        self.assertNotIn("Uploading conan_sources.tgz", client2.out)
        self.assertNotIn("Uploaded conan recipe 'hello0/1.2.1@frodo/stable' to 'default'",
                         client2.out)
        self.assertNotIn("Uploading conaninfo.txt", client2.out)  # conaninfo NOT changed
        self.assertNotIn("Uploading conan_package.tgz", client2.out)
        self.assertIn(f"{prev2.repr_notime()} already in server, skipping upload", client2.out)

        # first client tries to upload again
        refs = client.cache.get_latest_recipe_reference(ref)
        pkgs = client.cache.get_package_references(refs)
        prev1 = client.cache.get_latest_package_reference(pkgs[0])
        client.run("upload hello0/1.2.1@frodo/stable -r default")
        self.assertIn(f"{repr(prev1.ref)} already "
                      "in server, skipping upload", client.out)
        self.assertNotIn("Uploading conanfile.py", client.out)
        self.assertNotIn("Uploading conan_sources.tgz", client.out)
        self.assertNotIn("Uploaded conan recipe 'hello0/1.2.1@frodo/stable' to 'default'",
                         client.out)
        self.assertNotIn("Uploading conaninfo.txt", client.out)  # conaninfo NOT changed
        self.assertNotIn("Uploading conan_package.tgz", client2.out)
        self.assertIn(f"{prev1.repr_notime()} already in server, skipping upload", client2.out)

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
        self.assertIn("Uploading hello/1.0@frodo/stable", client.out)

        # CASE: Upload again
        client.run("upload hello/1.0@frodo/stable -r default")
        refs = client.cache.get_latest_recipe_reference(RecipeReference.loads("hello/1.0@frodo/stable"))
        pkgs = client.cache.get_package_references(refs)
        prev1 = client.cache.get_latest_package_reference(pkgs[0])
        self.assertIn(f"{repr(prev1.ref)} already "
                      "in server, skipping upload", client.out)
        self.assertIn(f"{prev1.repr_notime()} already in server, skipping upload", client.out)

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_skip_upload(self):
        """ Check that the option --skip does not upload anything
        """
        client = TestClient(default_server_user=True)

        files = {"conanfile.py": GenConanfile("hello0", "1.2.1").with_exports("*"),
                 "file.txt": ""}
        client.save(files)
        client.run("create . --user=frodo --channel=stable")
        client.run("upload hello0/1.2.1@frodo/stable -r default --skip-upload -r default")

        # dry run should not upload
        self.assertNotIn("Uploading conan_package.tgz", client.out)

        # but dry run should compress
        self.assertIn("Compressing recipe...", client.out)
        self.assertIn("Compressing package...", client.out)

        client.run("search -r default")
        # after dry run nothing should be on the server ...
        self.assertNotIn("hello0/1.2.1@frodo/stable", client.out)

        # now upload, the stuff should NOT be recompressed
        client.run("upload hello0/1.2.1@frodo/stable -r default -r default")

        # check for upload message
        self.assertIn("Uploading conan_package.tgz", client.out)

        # check if compressed files are re-used
        self.assertNotIn("Compressing recipe...", client.out)
        self.assertNotIn("Compressing package...", client.out)

        # now it should be on the server
        client.run("search -r default")
        self.assertIn("hello0/1.2.1@frodo/stable", client.out)

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
        self.assertIn("Uploading conanfile.py", client2.out)
        self.assertIn("Uploading conan_package.tgz", client2.out)

    def test_upload_login_prompt_disabled_no_user(self):
        """ Without user info, uploads should fail when login prompt has been disabled.
        """
        files = {"conanfile.py": GenConanfile("hello0", "1.2.1")}
        client = TestClient(default_server_user=True)
        client.save(files)
        conan_conf = "core:non_interactive=True"
        client.save({"global.conf": conan_conf}, path=client.cache.cache_folder)

        client.run("create . --user=user --channel=testing")
        client.run("remote logout '*'")
        client.run("upload hello0/1.2.1@user/testing -r default", assert_error=True)

        self.assertIn("Conan interactive mode disabled", client.out)
        self.assertNotIn("Uploading conanmanifest.txt", client.out)
        self.assertNotIn("Uploading conanfile.py", client.out)
        self.assertNotIn("Uploading conan_export.tgz", client.out)

    def test_upload_login_prompt_disabled_user_not_authenticated(self):
        # When a user is not authenticated, uploads should fail when login prompt has been disabled.
        files = {"conanfile.py": GenConanfile("hello0", "1.2.1")}
        client = TestClient(default_server_user=True)
        client.save(files)
        conan_conf = "core:non_interactive=True"
        client.save({"global.conf": conan_conf}, path=client.cache.cache_folder)
        client.run("create . --user=user --channel=testing")
        client.run("remote logout '*'")
        client.run("remote set-user default lasote")
        client.run("upload hello0/1.2.1@user/testing -r default", assert_error=True)
        self.assertIn("Conan interactive mode disabled", client.out)
        self.assertNotIn("Uploading conanmanifest.txt", client.out)
        self.assertNotIn("Uploading conanfile.py", client.out)
        self.assertNotIn("Uploading conan_export.tgz", client.out)
        self.assertNotIn("Please enter a password for", client.out)

    def test_upload_login_prompt_disabled_user_authenticated(self):
        #  When user is authenticated, uploads should work even when login prompt has been disabled.
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": GenConanfile("hello0", "1.2.1")})
        conan_conf = "core:non_interactive=True"
        client.save({"global.conf": conan_conf}, path=client.cache.cache_folder)
        client.run("create . --user=user --channel=testing")
        client.run("remote logout '*'")
        client.run("remote login default admin -p password")
        client.run("upload hello0/1.2.1@user/testing -r default")

        self.assertIn("Uploading conanmanifest.txt", client.out)
        self.assertIn("Uploading conanfile.py", client.out)

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
        client.run("remove * --force")
        client.run("install --requires=hello0/1.2.1@user/testing -r server1")
        client.run("remote remove server1")
        client.run("upload hello0/1.2.1@user/testing -r server2")
        self.assertNotIn("ERROR: 'server1'", client.out)

    @pytest.mark.xfail(reason="cache2.0: metadata test, check again in the future")
    def test_upload_export_pkg(self):
        """
        Package metadata created when doing an export-pkg and then uploading the package works
        """
        server1 = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")], users={"lasote": "mypass"})
        servers = OrderedDict()
        servers["server1"] = server1
        client = TestClient(servers=servers)
        client.save({"release/kk.lib": ""})
        client.run("user lasote -r server1 -p mypass")
        client.run("new hello/1.0 --header")
        client.run("export-pkg . user/testing -pf release")
        client.run("upload hello/1.0@user/testing -r server1")
        self.assertNotIn("Binary package hello/1.0@user/testing:5%s not found" %
                         NO_SETTINGS_PACKAGE_ID, client.out)
        ref = RecipeReference("hello", "1.0", "user", "testing")
        # FIXME: 2.0: load_metadata() method does not exist anymore
        metadata = client.get_latest_pkg_layout(pref).load_metadata()
        self.assertIn(NO_SETTINGS_PACKAGE_ID, metadata.packages)
        self.assertTrue(metadata.packages[NO_SETTINGS_PACKAGE_ID].revision)

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
        client2.create(ref, args="--build=*")
        client2.run("upload lib/1.0@conan/testing -r default")
        self.assertIn(f"lib/1.0@conan/testing#{rrev} already in "
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
        assert "Uploading lib/1.0" in client.out

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

        server = TestServer(users={"user": "password"}, write_permissions=[("*/*@*/*", "*")],
                            server_capabilities=[REVISIONS])
        servers = {"default": server}
        client = TestClient(requester_class=ServerCapabilitiesRequester, servers=servers,
                            inputs=["user", "password"])
        files = {"conanfile.py": GenConanfile("hello0", "1.2.1")}
        client.save(files)
        client.run("create . --user=user --channel=testing --build=*")
        client.run("remote logout '*'")
        client.run("upload hello0/1.2.1@user/testing -r default")
        assert "Uploading hello0/1.2.1@user/testing" in client.out

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_upload_with_recipe_revision(self):
        ref = RecipeReference.loads("pkg/1.0@user/channel")
        client = TurboTestClient(default_server_user=True)
        pref = client.create(ref, conanfile=GenConanfile())
        client.run("upload pkg/1.0@user/channel#fakerevision --confirm", assert_error=True)
        self.assertIn("ERROR: Recipe revision fakerevision does not match the one stored in "
                      "the cache {}".format(pref.ref.revision), client.out)

        client.run("upload pkg/1.0@user/channel#{} --confirm".format(pref.ref.revision))
        search_result = client.search("pkg/1.0@user/channel --revisions -r default")[0]
        self.assertIn(pref.ref.revision, search_result["revision"])

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_upload_with_package_revision(self):
        ref = RecipeReference.loads("pkg/1.0@user/channel")
        client = TurboTestClient(default_server_user=True)
        pref = client.create(ref, conanfile=GenConanfile())
        client.run("upload pkg/1.0@user/channel#{}:{}#fakeprev --confirm".format(pref.ref.revision,
                                                                                 pref.package_id),
                   assert_error=True)
        self.assertIn(
            "ERROR: Binary package pkg/1.0@user/channel:{}"
            "#fakeprev not found".format(pref.package_id),
            client.out)

        client.run(
            "upload pkg/1.0@user/channel#{}:{}#{} --confirm".format(pref.ref.revision,
                                                                    pref.package_id,
                                                                    pref.revision))
        search_result = client.search("pkg/1.0@user/channel --revisions -r default")[0]
        self.assertIn(pref.ref.revision, search_result["revision"])
        search_result = client.search(
            "pkg/1.0@user/channel#{}:{} --revisions  -r default".format(pref.ref.revision,
                                                                        pref.package_id))[
            0]
        self.assertIn(pref.revision, search_result["revision"])


@pytest.fixture(scope="module")
def populate_client():
    ret = defaultdict(list)
    client = TurboTestClient(default_server_user=True)

    package_lines = 'save(self, os.path.join(self.package_folder, "foo.txt"), ' \
                    'os.getenv("var_test", "Na"))'
    conanfile = str(GenConanfile().with_settings("build_type").with_package(package_lines)\
                              .with_import("from conan.tools.files import save")\
                              .with_import("import os")\
                              .with_import("import time"))
    for ref in [RecipeReference.loads("foo/1.0"), RecipeReference.loads("bar/1.1")]:
        for i in range(2):
            conanfile += "\n"*i  # Create 2 rrev
            for j in range(2):  # Create 2 prev
                with environment_update({'var_test': str(j)}):
                    pref = client.create(ref, args="-s build_type=Debug --build=*",
                                         conanfile=conanfile)
                    ret[pref.ref].append(pref)
                    pref = client.create(ref, args="-s build_type=Release --build=*",
                                         conanfile=conanfile)
                    ret[pref.ref].append(pref)
    return client, ret


def test_upload_recipe_selection(populate_client):
    client, refs = populate_client
    foo_rrevs = [r for r in refs.keys() if r.name == "foo"]
    bar_rrevs = [r for r in refs.keys() if r.name == "bar"]
    # Foo all revision upload
    for pattern in ("foo*", "foo/*", "f*"):
        # Clean the server test executions (client module scope)
        client.run("remove '*' -f -r default")
        # Upload the pattern
        client.run("upload {} -c -r default".format(pattern))
        # List recipes in the server
        client.run("list recipe-revisions foo/1.0 -r default")
        for ref in foo_rrevs:
            assert ref.repr_notime() in client.out
        client.run("list recipe-revisions bar/1.0 -r default")
        for ref in bar_rrevs:
            assert ref.repr_notime() not in client.out

    # All revisions upload
    for pattern in ("*", "*/*", "*/*#*"):
        # Clean the server test executions (client module scope)
        client.run("remove '*' -f -r default")
        # Upload the pattern
        client.run("upload {} -c -r default".format(pattern))
        # List recipes in the server
        client.run("list recipe-revisions foo/1.0 -r default")
        for ref in foo_rrevs:
            assert ref.repr_notime() in client.out
        client.run("list recipe-revisions bar/1.1 -r default")
        for ref in bar_rrevs:
            assert ref.repr_notime() in client.out

    # A single bar revision upload (latest)
    single_bar = bar_rrevs[1]
    for pattern in ("bar/1.*#{}".format(single_bar.revision),
                    "bar/1.*#{}*".format(single_bar.revision[0:6]),
                    "bar/1.*#latest"):
        # Clean the server test executions (client module scope)
        client.run("remove '*' -f -r default")
        # Upload the pattern
        client.run("upload {} -c -r default".format(pattern))
        # List recipes in the server
        client.run("list recipe-revisions foo/1.0 -r default")
        for ref in foo_rrevs:
            assert ref.repr_notime() not in client.out
        client.run("list recipe-revisions bar/1.1 -r default")
        for ref in bar_rrevs:
            if ref == single_bar:
                assert ref.repr_notime() in client.out
            else:
                assert ref.repr_notime() not in client.out


def test_upload_package_selection(populate_client):
    client, refs = populate_client

    def get_prev(ref, build_type, latest_prev):
        prevs = refs[ref]
        # [debug (#prev1), release (#prev1), debug (#prev2), release (#prev2)]
        if build_type == "Debug":
            return prevs[2] if latest_prev else prevs[0]
        return prevs[3] if latest_prev else prevs[1]

    foo_revs = [r for r in refs.keys() if r.name == "foo"]
    foo_first, foo_latest = foo_revs
    bar_revs = [r for r in refs.keys() if r.name == "bar"]
    bar_first, bar_latest = bar_revs

    # Uploading the recipe uploads all the package revisions
    # Clean the server test executions (client module scope)
    client.run("remove '*' -f -r default")
    # Upload the pattern
    client.run("upload foo/1.0 -c -r default")
    for ref in foo_revs:
        for pref in (get_prev(ref, "Release", True),
                     get_prev(ref, "Release", False),
                     get_prev(ref, "Debug", False),
                     get_prev(ref, "Debug", True)):
            tmp = PkgReference.loads(pref.repr_notime())
            tmp.revision = None
            client.run("list package-revisions {} -r default".format(tmp.repr_notime()))
            assert pref.repr_notime() in client.out

    # Foo all revision upload
    for pattern in ("foo/*#latest:*#latest",
                    "foo/*#{}:*#latest".format(foo_latest.revision)):
        # Clean the server test executions (client module scope)
        client.run("remove '*' -f -r default")
        # Upload the pattern
        client.run("upload {} -c -r default".format(pattern))
        # List package revisions in the server
        for pref in (get_prev(foo_latest, "Release", True), get_prev(foo_latest, "Debug", True)):
            tmp = PkgReference.loads(pref.repr_notime())
            tmp.revision = None
            client.run("list package-revisions {} -r default".format(tmp.repr_notime()))
            assert pref.repr_notime() in client.out

        for pref in (get_prev(foo_latest, "Release", False), get_prev(foo_latest, "Debug", False)):
            tmp = PkgReference.loads(pref.repr_notime())
            tmp.revision = None
            client.run("list package-revisions {} -r default".format(tmp.repr_notime()))
            assert pref.repr_notime() not in client.out

    # Only the release package from the latest revision and the latest package revision
    for pattern in ("foo/*#latest:*#latest -p 'build_type=Release'",
                    "foo/*#{}:*#latest -p 'build_type=Release'".format(foo_latest.revision)):
        # Clean the server test executions (client module scope)
        client.run("remove '*' -f -r default")
        # Upload the pattern
        client.run("upload {} -c -r default".format(pattern))
        # List package revisions in the server
        pref = get_prev(foo_latest, "Release", True)
        tmp = PkgReference.loads(pref.repr_notime())
        tmp.revision = None
        client.run("list package-revisions {} -r default".format(tmp.repr_notime()))
        assert pref.repr_notime() in client.out

        # No Debug packages and not the release not latest prev
        for pref in (get_prev(foo_latest, "Release", False),
                     get_prev(foo_latest, "Debug", False),
                     get_prev(foo_latest, "Debug", True)):
            tmp = PkgReference.loads(pref.repr_notime())
            tmp.revision = None
            client.run("list package-revisions {} -r default".format(tmp.repr_notime()))
            assert pref.repr_notime() not in client.out

    # Upload a fixed prev
    client.run("remove '*' -f -r default")
    prev = get_prev(bar_first, "Release", True)
    client.run("upload {} -c -r default".format(prev.repr_notime()))
    tmp = PkgReference.loads(prev.repr_notime())
    tmp.revision = None
    client.run("list package-revisions {} -r default".format(tmp.repr_notime()))
    assert prev.repr_notime() in client.out
    for prev in (get_prev(bar_first, "Release", False),
                 get_prev(bar_first, "Debug", True),
                 get_prev(bar_first, "Debug", False),
                 get_prev(bar_latest, "Release", True),
                 get_prev(bar_latest, "Debug", False),
                 get_prev(bar_latest, "Release", False),
                 get_prev(bar_latest, "Debug", True)):
        tmp = PkgReference.loads(prev.repr_notime())
        tmp.revision = None
        client.run("list package-revisions {} -r default".format(tmp.repr_notime()))
        assert prev.repr_notime() not in client.out
    # The recipe also uploaded
    tmp = RecipeReference.loads(bar_first.repr_notime())
    tmp.revision = None
    client.run("list recipe-revisions {} -r default".format(tmp.repr_notime()))
    assert bar_first.repr_notime() in client.out

    # Debug both prevs
    client.run("remove '*' -f -r default")
    prev = get_prev(bar_first, "Debug", True)
    tmp = PkgReference.loads(prev.repr_notime())
    tmp.ref.revision = "*"
    tmp.revision = "*"
    client.run("upload {} -c -r default".format(tmp.repr_notime()))
    tmp = PkgReference.loads(prev.repr_notime())
    tmp.revision = None
    client.run("list package-revisions {} -r default".format(tmp.repr_notime()))
    assert prev.repr_notime() in client.out
    for prev in (get_prev(bar_first, "Debug", True),
                 get_prev(bar_first, "Debug", False),
                 get_prev(bar_latest, "Debug", True),
                 get_prev(bar_latest, "Debug", False)):
        tmp = copy(prev)
        tmp.revision = None
        client.run("list package-revisions {} -r default".format(tmp.repr_notime()))
        assert prev.repr_notime() in client.out

    for prev in (get_prev(bar_first, "Release", True),
                 get_prev(bar_first, "Release", False),
                 get_prev(bar_latest, "Release", True),
                 get_prev(bar_latest, "Release", False)):
        tmp = copy(prev)
        tmp.revision = None
        client.run("list package-revisions {} -r default".format(tmp.repr_notime()))
        assert prev.repr_notime() not in client.out


def test_upload_only_without_user_channel():
    """
    check that we can upload only the packages without user and channel
    https://github.com/conan-io/conan/issues/10579
    """
    c = TestClient(default_server_user=True)

    c.save({"conanfile.py": GenConanfile("lib", "1.0")})
    c.run('create .')
    c.run("create . --user=user --channel=channel")
    c.run("list recipes *")
    assert "lib/1.0@user/channel" in c.out

    c.run('upload */*@ -c -r=default')
    assert "Uploading lib/1.0" in c.out  # FAILS!
    assert "lib/1.0@user/channel" not in c.out
    c.run("search * -r=default")
    assert "lib/1.0" in c.out
    assert "lib/1.0@user/channel" not in c.out

    c.run('upload */*@user/channel -c -r=default')
    assert "Uploading lib/1.0@user/channel" in c.out
    c.run("search * -r=default")
    assert "lib/1.0@user/channel" in c.out
    assert "lib/1.0" in c.out
