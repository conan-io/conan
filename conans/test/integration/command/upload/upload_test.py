import itertools
import os
import platform
import stat
import textwrap
import unittest
from collections import OrderedDict

import pytest
import requests
from mock import patch

from conans import REVISIONS
from conans.client.tools.env import environment_append
from conans.errors import ConanException
from conans.model.package_ref import PkgReference
from conans.model.ref import ConanFileReference
from conans.paths import EXPORT_SOURCES_TGZ_NAME, PACKAGE_TGZ_NAME
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, TestServer, \
    TurboTestClient, GenConanfile, TestRequester, TestingResponse
from conans.util.files import gzopen_without_timestamps, is_dirty, save, set_dirty

conanfile = """from conans import ConanFile
class MyPkg(ConanFile):
    name = "Hello0"
    version = "1.2.1"
    exports_sources = "*"

    def package(self):
        self.copy("*")
"""


class UploadTest(unittest.TestCase):

    @pytest.mark.xfail(reason="cache2.0 will remove -p make sense for 2.0?")
    def test_upload_dirty(self):
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": GenConanfile("Hello", "0.1")})
        client.run("create . lasote/testing")
        ref = ConanFileReference.loads("Hello/0.1@lasote/testing")

        rrev = client.cache.get_latest_rrev(ref)
        prev = client.cache.get_latest_prev(rrev)
        pkg_folder = client.cache.pkg_layout(prev).package()
        set_dirty(pkg_folder)

        client.run("upload * --all --confirm", assert_error=True)
        self.assertIn(f"ERROR: Hello/0.1@lasote/testing:{NO_SETTINGS_PACKAGE_ID}: "
                      "Upload package to 'default' failed: Package %s is corrupted, aborting upload"
                      % str(prev), client.out)
        self.assertIn("Remove it with 'conan remove Hello/0.1@lasote/testing -p=%s'"
                      % NO_SETTINGS_PACKAGE_ID, client.out)

        # TODO: cache2.0 check if this makes sense for 2.0, xfail test for the moment
        client.run("remove Hello/0.1@lasote/testing -p=%s -f" % NO_SETTINGS_PACKAGE_ID)
        client.run("upload * --all --confirm")

    @pytest.mark.artifactory_ready
    def test_upload_force(self):
        ref = ConanFileReference.loads("Hello/0.1@conan/testing")
        client = TurboTestClient(default_server_user=True)
        pref = client.create(ref, conanfile=GenConanfile().with_package_file("myfile.sh", "foo"))
        client.run("upload * --all --confirm -r default")
        self.assertIn("Uploading conan_package.tgz", client.out)
        client.run("upload * --all --confirm -r default")
        self.assertNotIn("Uploading conan_package.tgz", client.out)

        package_folder = client.get_latest_pkg_layout(pref).package()
        package_file_path = os.path.join(package_folder, "myfile.sh")

        if platform.system() == "Linux":
            client.run("remove '*' -f")
            client.create(ref, conanfile=GenConanfile().with_package_file("myfile.sh", "foo"))
            os.system('chmod +x "{}"'.format(package_file_path))
            self.assertTrue(os.stat(package_file_path).st_mode & stat.S_IXUSR)
            client.run("upload * --all --confirm -r default")
            # Doesn't change revision, doesn't reupload
            self.assertNotIn("Uploading conan_package.tgz", client.out)
            self.assertIn("skipping upload", client.out)
            self.assertNotIn("Compressing package...", client.out)

        # with --force it really re-uploads it
        client.run("upload * --all --confirm --force -r default")
        self.assertIn("Uploading conanfile.py", client.out)
        self.assertIn("Uploading conan_package.tgz", client.out)

        if platform.system() == "Linux":
            client.run("remove '*' -f")
            client.run("install {}".format(ref))
            # Owner with execute permissions
            self.assertTrue(os.stat(package_file_path).st_mode & stat.S_IXUSR)

    def test_upload_binary_not_existing(self):
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": GenConanfile()})
        client.run("export . Hello/0.1@lasote/testing")
        client.run("upload Hello/0.1@lasote/testing -p=123 -r default", assert_error=True)
        self.assertIn("ERROR: Binary package Hello/0.1@lasote/testing:123 not found", client.out)

    def test_not_existing_error(self):
        """ Trying to upload with pattern not matched must raise an Error
        """
        client = TestClient(default_server_user=True)
        client.run("upload some_nonsense -r default", assert_error=True)
        self.assertIn("ERROR: No packages found matching pattern 'some_nonsense'",
                      client.out)

    def test_invalid_reference_error(self):
        """ Trying to upload an invalid reference must raise an Error
        """
        client = TestClient(default_server_user=True)
        client.run("upload some_nonsense -p hash1 -r default", assert_error=True)
        self.assertIn("ERROR: -p parameter only allowed with a valid recipe reference",
                      client.out)

    def test_non_existing_recipe_error(self):
        """ Trying to upload a non-existing recipe must raise an Error
        """
        client = TestClient(default_server_user=True)
        client.run("upload Pkg/0.1@user/channel -r default", assert_error=True)
        self.assertIn("Recipe not found: 'Pkg/0.1@user/channel'", client.out)

    def test_non_existing_package_error(self):
        """ Trying to upload a non-existing package must raise an Error
        """
        client = TestClient(default_server_user=True)
        client.run("upload Pkg/0.1@user/channel -p hash1 -r default", assert_error=True)
        self.assertIn("ERROR: Recipe not found: 'Pkg/0.1@user/channel'", client.out)

    def test_deprecated_p_arg(self):
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": conanfile})
        client.run("create . user/testing")
        client.run("upload Hello0/1.2.1@user/testing -p {} -c -r default".format(NO_SETTINGS_PACKAGE_ID))
        self.assertIn("WARN: Usage of `--package` argument is deprecated. "
                      "Use a full reference instead: `conan upload [...] "
                      "Hello0/1.2.1@user/testing:{}`".format(NO_SETTINGS_PACKAGE_ID), client.out)

    def test_upload_with_pref(self):
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": conanfile})
        client.run("create . user/testing")
        client.run("upload Hello0/1.2.1@user/testing:{} -c -r default".format(NO_SETTINGS_PACKAGE_ID))
        self.assertNotIn("WARN: Usage of `--package` argument is deprecated. "
                         "Use a full reference instead: `conan upload [...] "
                         "Hello0/1.2.1@user/testing:{}`".format(NO_SETTINGS_PACKAGE_ID),
                         client.out)
        self.assertIn("Uploading package 1/1: {} to 'default'".format(NO_SETTINGS_PACKAGE_ID),
                      client.out)

    def test_upload_with_pref_and_p(self):
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": conanfile})
        client.run("create . user/testing")
        client.run("upload Hello0/1.2.1@user/testing:{} -c -p {} -r default".format(NO_SETTINGS_PACKAGE_ID,
                                                                         NO_SETTINGS_PACKAGE_ID),
                   assert_error=True)

        self.assertIn("Use a full package reference (preferred) or the "
                      "`--package` command argument, but not both.", client.out)

    def test_pattern_upload(self):
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": conanfile})
        client.run("create . user/testing")
        client.run("upload Hello0/*@user/testing --confirm --all -r default")
        self.assertIn("Uploading conanmanifest.txt", client.out)
        self.assertIn("Uploading conan_package.tgz", client.out)
        self.assertIn("Uploading conanfile.py", client.out)

    @pytest.mark.xfail(reason="cache2.0 query not yet implemented")
    def test_query_upload(self):
        client = TestClient(default_server_user=True)
        conanfile_upload_query = textwrap.dedent("""
            from conans import ConanFile
            class MyPkg(ConanFile):
                name = "Hello1"
                version = "1.2.1"
                exports_sources = "*"
                settings = "os", "arch"

                def package(self):
                    self.copy("*")
            """)
        client.save({"conanfile.py": conanfile_upload_query})

        for _os, arch in itertools.product(["Macos", "Linux", "Windows"],
                                           ["armv8", "x86_64"]):
            client.run("create . user/testing -s os=%s -s arch=%s" % (_os, arch))

        # Check that the right number of packages are picked up by the queries
        client.run("upload Hello1/*@user/testing --confirm -q 'os=Windows or os=Macos' -r default")
        for i in range(1, 5):
            self.assertIn("Uploading package %d/4" % i, client.out)
        self.assertNotIn("Package is up to date, upload skipped", client.out)

        client.run("upload Hello1/*@user/testing --confirm -q 'os=Linux and arch=x86_64' -r default")
        self.assertIn("Uploading package 1/1", client.out)

        client.run("upload Hello1/*@user/testing --confirm -q 'arch=armv8' -r default")
        for i in range(1, 4):
            self.assertIn("Uploading package %d/3" % i, client.out)
        self.assertIn("Package is up to date, upload skipped", client.out)

        # Check that a query not matching any packages doesn't upload any packages
        client.run("upload Hello1/*@user/testing --confirm -q 'arch=sparc' -r default")
        self.assertNotIn("Uploading package", client.out)

        # Check that an invalid query fails
        client.run("upload Hello1/*@user/testing --confirm -q 'blah blah blah' -r default", assert_error=True)
        self.assertIn("Invalid package query", client.out)

    def test_broken_sources_tgz(self):
        # https://github.com/conan-io/conan/issues/2854
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": conanfile,
                     "source.h": "my source"})
        client.run("create . user/testing")
        ref = ConanFileReference.loads("Hello0/1.2.1@user/testing")

        def gzopen_patched(name, mode="r", fileobj=None, **kwargs):
            raise ConanException("Error gzopen %s" % name)
        with patch('conans.client.cmd.uploader.gzopen_without_timestamps', new=gzopen_patched):
            client.run("upload * --confirm -r default", assert_error=True)
            self.assertIn("ERROR: Hello0/1.2.1@user/testing: Upload recipe to 'default' failed: "
                          "Error gzopen conan_sources.tgz", client.out)

            latest_rrev = client.cache.get_latest_rrev(ref)
            export_download_folder = client.cache.ref_layout(latest_rrev).download_export()

            tgz = os.path.join(export_download_folder, EXPORT_SOURCES_TGZ_NAME)
            self.assertTrue(os.path.exists(tgz))
            self.assertTrue(is_dirty(tgz))

        client.run("upload * --confirm -r default")
        self.assertIn("WARN: Hello0/1.2.1@user/testing: Removing conan_sources.tgz, "
                      "marked as dirty", client.out)
        self.assertTrue(os.path.exists(tgz))
        self.assertFalse(is_dirty(tgz))

    def test_broken_package_tgz(self):
        # https://github.com/conan-io/conan/issues/2854
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": conanfile,
                     "source.h": "my source"})
        client.run("create . user/testing")
        pref = client.get_latest_prev(ConanFileReference.loads("Hello0/1.2.1@user/testing"),
                                      NO_SETTINGS_PACKAGE_ID)

        def gzopen_patched(name, mode="r", fileobj=None, **kwargs):
            if name == PACKAGE_TGZ_NAME:
                raise ConanException("Error gzopen %s" % name)
            return gzopen_without_timestamps(name, mode, fileobj, **kwargs)
        with patch('conans.client.cmd.uploader.gzopen_without_timestamps', new=gzopen_patched):
            client.run("upload * --confirm --all -r default", assert_error=True)
            self.assertIn(f"ERROR: Hello0/1.2.1@user/testing:{NO_SETTINGS_PACKAGE_ID}: "
                          "Upload package to 'default' failed: Error gzopen conan_package.tgz",
                          client.out)

            download_folder = client.get_latest_pkg_layout(pref).download_package()
            tgz = os.path.join(download_folder, PACKAGE_TGZ_NAME)
            self.assertTrue(os.path.exists(tgz))
            self.assertTrue(is_dirty(tgz))

        client.run("upload * --confirm --all -r default")
        self.assertIn("WARN: Hello0/1.2.1@user/testing:%s: "
                      "Removing conan_package.tgz, marked as dirty" % NO_SETTINGS_PACKAGE_ID,
                      client.out)
        self.assertTrue(os.path.exists(tgz))
        self.assertFalse(is_dirty(tgz))

    def test_corrupt_upload(self):
        client = TestClient(default_server_user=True)

        client.save({"conanfile.py": conanfile,
                     "include/hello.h": ""})
        client.run("create . frodo/stable")
        ref = ConanFileReference.loads("Hello0/1.2.1@frodo/stable")
        latest_rrev = client.cache.get_latest_rrev(ref)
        pkg_ids = client.cache.get_package_references(latest_rrev)
        latest_prev = client.cache.get_latest_prev(pkg_ids[0])
        package_folder = client.cache.pkg_layout(latest_prev).package()
        save(os.path.join(package_folder, "added.txt"), "")
        os.remove(os.path.join(package_folder, "include/hello.h"))
        client.run("upload Hello0/1.2.1@frodo/stable --all --check -r default", assert_error=True)
        self.assertIn("WARN: Mismatched checksum 'added.txt'", client.out)
        self.assertIn("WARN: Mismatched checksum 'include/hello.h'", client.out)
        self.assertIn(f"ERROR: Hello0/1.2.1@frodo/stable:{NO_SETTINGS_PACKAGE_ID}: "
                      "Upload package to 'default' failed: Cannot upload corrupted package",
                      client.out)

    def test_upload_modified_recipe(self):
        client = TestClient(default_server_user=True)

        client.save({"conanfile.py": conanfile,
                     "hello.cpp": "int i=0"})
        client.run("export . frodo/stable")
        client.run("upload Hello0/1.2.1@frodo/stable -r default")
        self.assertIn("Uploading conanmanifest.txt", client.out)
        assert "Uploading Hello0/1.2.1@frodo/stable to remote" in client.out

        client2 = TestClient(servers=client.servers, inputs=["admin", "password"])
        client2.save({"conanfile.py": conanfile + "\r\n#end",
                      "hello.cpp": "int i=1"})
        client2.run("export . frodo/stable")
        ref = ConanFileReference.loads("Hello0/1.2.1@frodo/stable")
        latest_rrev = client2.cache.get_latest_rrev(ref)
        manifest = client2.cache.ref_layout(latest_rrev).recipe_manifest()
        manifest.time += 10
        manifest.save(client2.cache.ref_layout(latest_rrev).export())
        client2.run("upload Hello0/1.2.1@frodo/stable -r default")
        self.assertIn("Uploading conanmanifest.txt", client2.out)
        assert "Uploading Hello0/1.2.1@frodo/stable to remote" in client2.out

        # first client tries to upload again
        # The client tries to upload exactly the same revision already uploaded, so no changes
        client.run("upload Hello0/1.2.1@frodo/stable -r default")
        self.assertIn("Hello0/1.2.1@frodo/stable#fa605b28327765a3262329cf4d30baec already "
                      "in server, skipping upload", client.out)

    def test_upload_unmodified_recipe(self):
        client = TestClient(default_server_user=True)
        files = {"conanfile.py": GenConanfile("Hello0", "1.2.1")}
        client.save(files)
        client.run("export . frodo/stable")
        client.run("upload Hello0/1.2.1@frodo/stable -r default")
        self.assertIn("Uploading conanmanifest.txt", client.out)
        assert "Uploading Hello0/1.2.1@frodo/stable to remote" in client.out

        client2 = TestClient(servers=client.servers, inputs=["admin", "password"])
        client2.save(files)
        client2.run("export . frodo/stable")
        ref = ConanFileReference.loads("Hello0/1.2.1@frodo/stable")
        rrev = client2.cache.get_latest_rrev(ref)
        manifest = client2.cache.ref_layout(rrev).recipe_manifest()
        manifest.time += 10
        manifest.save(client2.cache.ref_layout(rrev).export())
        client2.run("upload Hello0/1.2.1@frodo/stable -r default")
        self.assertNotIn("Uploading conanmanifest.txt", client2.out)
        assert "Uploading Hello0/1.2.1@frodo/stable to remote" in client2.out
        self.assertIn("Hello0/1.2.1@frodo/stable#90e049fdc1330bfb8b1f82d311f46f50 already "
                      "in server, skipping upload", client2.out)

        # first client tries to upload again
        client.run("upload Hello0/1.2.1@frodo/stable -r default")
        self.assertNotIn("Uploading conanmanifest.txt", client.out)
        assert "Uploading Hello0/1.2.1@frodo/stable to remote" in client.out
        self.assertIn("Hello0/1.2.1@frodo/stable#90e049fdc1330bfb8b1f82d311f46f50 "
                      "already in server, skipping upload", client.out)

    def test_upload_unmodified_package(self):
        client = TestClient(default_server_user=True)

        client.save({"conanfile.py": conanfile,
                     "hello.cpp": ""})
        client.run("create . frodo/stable")
        client.run("upload Hello0/1.2.1@frodo/stable --all -r default")

        client2 = TestClient(servers=client.servers, inputs=["admin", "password"])
        client2.save({"conanfile.py": conanfile,
                      "hello.cpp": ""})
        client2.run("create . frodo/stable")
        client2.run("upload Hello0/1.2.1@frodo/stable --all -r default")
        self.assertIn("Hello0/1.2.1@frodo/stable#37545dd5551161db93addff8b6bd2aea already "
                      "in server, skipping upload", client2.out)
        self.assertNotIn("Uploading conanfile.py", client2.out)
        self.assertNotIn("Uploading conan_sources.tgz", client2.out)
        self.assertNotIn("Uploaded conan recipe 'Hello0/1.2.1@frodo/stable' to 'default'",
                         client2.out)
        self.assertNotIn("Uploading conaninfo.txt", client2.out)  # conaninfo NOT changed
        self.assertNotIn("Uploading conan_package.tgz", client2.out)
        self.assertIn("Hello0/1.2.1@frodo/stable#37545dd5551161db93addff8b6bd2aea:"
                      "357add7d387f11a959f3ee7d4fc9c2487dbaa604#9040c90925bc0cb0a3ba3ce7db39166b"
                      " already in server, skipping upload", client2.out)

        # first client tries to upload again
        client.run("upload Hello0/1.2.1@frodo/stable --all -r default")
        self.assertIn("Hello0/1.2.1@frodo/stable#37545dd5551161db93addff8b6bd2aea already "
                      "in server, skipping upload", client.out)
        self.assertNotIn("Uploading conanfile.py", client.out)
        self.assertNotIn("Uploading conan_sources.tgz", client.out)
        self.assertNotIn("Uploaded conan recipe 'Hello0/1.2.1@frodo/stable' to 'default'",
                         client.out)
        self.assertNotIn("Uploading conaninfo.txt", client.out)  # conaninfo NOT changed
        self.assertNotIn("Uploading conan_package.tgz", client2.out)
        self.assertIn("Hello0/1.2.1@frodo/stable#37545dd5551161db93addff8b6bd2aea:"
                      "357add7d387f11a959f3ee7d4fc9c2487dbaa604#9040c90925bc0cb0a3ba3ce7db39166b"
                      " already in server, skipping upload", client2.out)

    def test_upload_no_overwrite_all(self):
        conanfile_new = """from conans import ConanFile, tools
class MyPkg(ConanFile):
    name = "Hello0"
    version = "1.2.1"
    exports_sources = "*"
    options = {"shared": [True, False]}
    default_options = {"shared": False}

    def build(self):
        if tools.get_env("MY_VAR", False):
            open("file.h", 'w').close()

    def package(self):
        self.copy("*.h")
"""
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": conanfile_new,
                     "hello.h": "",
                     "hello.cpp": ""})
        client.run("create . frodo/stable")

        # First time upload
        client.run("upload Hello0/1.2.1@frodo/stable --all -r default")
        self.assertNotIn("Forbidden overwrite", client.out)
        self.assertIn("Uploading Hello0/1.2.1@frodo/stable", client.out)

        # CASE: Upload again
        client.run("upload Hello0/1.2.1@frodo/stable --all -r default")
        self.assertIn("Hello0/1.2.1@frodo/stable#64111bb02374de41afe658628c4b9aa1 already "
                      "in server, skipping upload", client.out)
        self.assertIn("Hello0/1.2.1@frodo/stable#64111bb02374de41afe658628c4b9aa1:"
                      "ce10536a7f7b9acce4e1f28ea4ee8e3973be0f6f#8d88cd7a53908e15c9241db4ed0b5808"
                      " already in server, skipping upload", client.out)
        self.assertNotIn("Forbidden overwrite", client.out)

        # CASE: Without changes
        client.run("create . frodo/stable")
        # upload recipe and packages
        client.run("upload Hello0/1.2.1@frodo/stable --all -r default")
        self.assertIn("Hello0/1.2.1@frodo/stable#64111bb02374de41afe658628c4b9aa1 already "
                      "in server, skipping upload", client.out)
        self.assertIn("Hello0/1.2.1@frodo/stable#64111bb02374de41afe658628c4b9aa1:"
                      "ce10536a7f7b9acce4e1f28ea4ee8e3973be0f6f#8d88cd7a53908e15c9241db4ed0b5808"
                      " already in server, skipping upload", client.out)
        self.assertNotIn("Forbidden overwrite", client.out)

        # CASE: When recipe and package changes
        new_recipe = conanfile_new.replace("self.copy(\"*.h\")",
                                           "self.copy(\"*.h\")\n        self.copy(\"*.cpp\")")
        client.save({"conanfile.py": new_recipe})
        client.run("create . frodo/stable")
        # upload recipe and packages
        # *1
        client.run("upload Hello0/1.2.1@frodo/stable --all -r default")

        # CASE: When package changes
        client.run("upload Hello0/1.2.1@frodo/stable --all -r default")
        with environment_append({"MY_VAR": "True"}):
            client.run("create . frodo/stable")
        # upload recipe and packages
        client.run("upload Hello0/1.2.1@frodo/stable --all -r default")
        self.assertIn("Uploading conan_package.tgz", client.out)

    def test_upload_no_overwrite_recipe(self):
        conanfile_new = """from conans import ConanFile, tools
class MyPkg(ConanFile):
    name = "Hello0"
    version = "1.2.1"
    exports_sources = "*"
    options = {"shared": [True, False]}
    default_options = {"shared": False}

    def build(self):
        if tools.get_env("MY_VAR", False):
            open("file.h", 'w').close()

    def package(self):
        self.copy("*.h")
"""
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": conanfile_new,
                     "hello.h": "",
                     "hello.cpp": ""})
        client.run("create . frodo/stable")

        # First time upload
        client.run("upload Hello0/1.2.1@frodo/stable --all -r default")
        self.assertNotIn("Forbidden overwrite", client.out)
        self.assertIn("Uploading Hello0/1.2.1@frodo/stable", client.out)

        # Upload again
        client.run("upload Hello0/1.2.1@frodo/stable --all -r default")
        self.assertIn("Hello0/1.2.1@frodo/stable#64111bb02374de41afe658628c4b9aa1 already "
                      "in server, skipping upload", client.out)
        self.assertIn("Hello0/1.2.1@frodo/stable#64111bb02374de41afe658628c4b9aa1:"
                      "ce10536a7f7b9acce4e1f28ea4ee8e3973be0f6f#8d88cd7a53908e15c9241db4ed0b5808"
                      " already in server, skipping upload", client.out)
        self.assertNotIn("Forbidden overwrite", client.out)

        # Create without changes
        # *1
        client.run("create . frodo/stable")
        client.run("upload Hello0/1.2.1@frodo/stable --all -r default")
        self.assertIn("Hello0/1.2.1@frodo/stable#64111bb02374de41afe658628c4b9aa1 already in "
                      "server, skipping upload", client.out)
        self.assertIn("Hello0/1.2.1@frodo/stable#64111bb02374de41afe658628c4b9aa1:"
                      "ce10536a7f7b9acce4e1f28ea4ee8e3973be0f6f#8d88cd7a53908e15c9241db4ed0b5808"
                      " already in server, skipping upload", client.out)
        self.assertNotIn("Forbidden overwrite", client.out)

        # Create with recipe and package changes
        new_recipe = conanfile_new.replace("self.copy(\"*.h\")",
                                           "self.copy(\"*.h\")\n        self.copy(\"*.cpp\")")
        client.save({"conanfile.py": new_recipe})
        client.run("create . frodo/stable")
        # upload recipe and packages
        client.run("upload Hello0/1.2.1@frodo/stable --all -r default")
        self.assertIn("Uploading conan_package.tgz", client.out)

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_skip_upload(self):
        """ Check that the option --skip does not upload anything
        """
        client = TestClient(default_server_user=True)

        files = {"conanfile.py": GenConanfile("Hello0", "1.2.1").with_exports("*"),
                 "file.txt": ""}
        client.save(files)
        client.run("create . frodo/stable")
        client.run("upload Hello0/1.2.1@frodo/stable -r default --all --skip-upload -r default")

        # dry run should not upload
        self.assertNotIn("Uploading conan_package.tgz", client.out)

        # but dry run should compress
        self.assertIn("Compressing recipe...", client.out)
        self.assertIn("Compressing package...", client.out)

        client.run("search -r default")
        # after dry run nothing should be on the server ...
        self.assertNotIn("Hello0/1.2.1@frodo/stable", client.out)

        # now upload, the stuff should NOT be recompressed
        client.run("upload Hello0/1.2.1@frodo/stable -r default --all -r default")

        # check for upload message
        self.assertIn("Uploading conan_package.tgz", client.out)

        # check if compressed files are re-used
        self.assertNotIn("Compressing recipe...", client.out)
        self.assertNotIn("Compressing package...", client.out)

        # now it should be on the server
        client.run("search -r default")
        self.assertIn("Hello0/1.2.1@frodo/stable", client.out)

    def test_upload_without_sources(self):
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . Pkg/0.1@user/testing")
        client.run("upload * --all --confirm -r default")
        client2 = TestClient(servers=client.servers, inputs=["admin", "password",
                                                             "lasote", "mypass"])

        client2.run("install Pkg/0.1@user/testing")
        client2.run("remote remove default")
        server2 = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")],
                             users={"lasote": "mypass"})
        client2.servers = {"server2": server2}
        client2.update_servers()
        client2.run("upload * --all --confirm -r=server2")
        self.assertIn("Uploading conanfile.py", client2.out)
        self.assertIn("Uploading conan_package.tgz", client2.out)

    def test_upload_login_prompt_disabled_no_user(self):
        """ Without user info, uploads should fail when login prompt has been disabled.
        """
        files = {"conanfile.py": GenConanfile("Hello0", "1.2.1")}
        client = TestClient(default_server_user=True)
        client.save(files)
        conan_conf = textwrap.dedent("""
                                    [storage]
                                    path = ./data
                                    [general]
                                    non_interactive=True
                                """)
        client.save({"conan.conf": conan_conf}, path=client.cache.cache_folder)

        client.run("create . user/testing")
        client.run("remote logout '*'")
        client.run("upload Hello0/1.2.1@user/testing -r default", assert_error=True)

        self.assertIn("ERROR: Hello0/1.2.1@user/testing: Upload recipe to 'default' failed: "
                      "Conan interactive mode disabled", client.out)
        self.assertNotIn("Uploading conanmanifest.txt", client.out)
        self.assertNotIn("Uploading conanfile.py", client.out)
        self.assertNotIn("Uploading conan_export.tgz", client.out)

    def test_upload_login_prompt_disabled_user_not_authenticated(self):
        # When a user is not authenticated, uploads should fail when login prompt has been disabled.
        files = {"conanfile.py": GenConanfile("Hello0", "1.2.1")}
        client = TestClient(default_server_user=True)
        client.save(files)
        conan_conf = textwrap.dedent("""
                                    [storage]
                                    path = ./data
                                    [general]
                                    non_interactive=True
                                """)
        client.save({"conan.conf": conan_conf}, path=client.cache.cache_folder)
        client.run("create . user/testing")
        client.run("remote logout '*'")
        client.run("remote set-user default lasote")
        client.run("upload Hello0/1.2.1@user/testing -r default", assert_error=True)
        self.assertIn("ERROR: Hello0/1.2.1@user/testing: Upload recipe to 'default' failed: "
                      "Conan interactive mode disabled", client.out)
        self.assertNotIn("Uploading conanmanifest.txt", client.out)
        self.assertNotIn("Uploading conanfile.py", client.out)
        self.assertNotIn("Uploading conan_export.tgz", client.out)
        self.assertNotIn("Please enter a password for", client.out)

    def test_upload_login_prompt_disabled_user_authenticated(self):
        #  When user is authenticated, uploads should work even when login prompt has been disabled.
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": GenConanfile("Hello0", "1.2.1")})
        conan_conf = textwrap.dedent("""
                                    [storage]
                                    path = ./data
                                    [general]
                                    non_interactive=True
                                """)
        client.save({"conan.conf": conan_conf}, path=client.cache.cache_folder)
        client.run("create . user/testing")
        client.run("remote logout '*'")
        client.run("remote login default admin -p password")
        client.run("upload Hello0/1.2.1@user/testing -r default")

        self.assertIn("Uploading conanmanifest.txt", client.out)
        self.assertIn("Uploading conanfile.py", client.out)

    def test_upload_key_error(self):
        files = {"conanfile.py": GenConanfile("Hello0", "1.2.1")}
        server1 = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")], users={"lasote": "mypass"})
        server2 = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")], users={"lasote": "mypass"})
        servers = OrderedDict()
        servers["server1"] = server1
        servers["server2"] = server2
        client = TestClient(servers=servers)
        client.save(files)
        client.run("create . user/testing")
        client.run("remote login server1 lasote -p mypass")
        client.run("remote login server2 lasote -p mypass")
        client.run("upload Hello0/1.2.1@user/testing --all -r server1")
        client.run("remove * --force")
        client.run("install Hello0/1.2.1@user/testing -r server1")
        client.run("remote remove server1")
        client.run("upload Hello0/1.2.1@user/testing --all -r server2")
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
        client.run("upload hello/1.0@user/testing --all -r server1")
        self.assertNotIn("Binary package hello/1.0@user/testing:5%s not found" %
                         NO_SETTINGS_PACKAGE_ID, client.out)
        ref = ConanFileReference("hello", "1.0", "user", "testing")
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

        ref = ConanFileReference.loads("lib/1.0@conan/testing")
        client.create(ref)
        client.upload_all(ref)
        # Upload same with client2
        client2.create(ref)
        client2.run("upload lib/1.0@conan/testing -r default")
        self.assertIn("lib/1.0@conan/testing#f3367e0e7d170aa12abccb175fee5f97 already in "
                      "server, skipping upload", client2.out)
        self.assertNotIn("WARN", client2.out)

    def test_upload_with_pref_and_query(self):
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": conanfile})
        client.run("create . user/testing")
        client.run("upload Hello0/1.2.1@user/testing:{} "
                   "-q 'os=Windows or os=Macos' -r default".format(NO_SETTINGS_PACKAGE_ID),
                   assert_error=True)

        self.assertIn("'--query' argument cannot be used together with full reference", client.out)

    def test_upload_with_package_id_and_query(self):
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": conanfile})
        client.run("create . user/testing")
        client.run("upload Hello0/1.2.1@user/testing -p {} "
                   "-q 'os=Windows or os=Macos' -r default".format(NO_SETTINGS_PACKAGE_ID),
                   assert_error=True)

        self.assertIn("'--query' argument cannot be used together with '--package'", client.out)

    def test_upload_without_user_channel(self):
        server = TestServer(users={"user": "password"}, write_permissions=[("*/*@*/*", "*")])
        servers = {"default": server}
        client = TestClient(servers=servers, inputs=["user", "password"])

        client.save({"conanfile.py": GenConanfile()})

        client.run('create . lib/1.0@')
        self.assertIn("lib/1.0: Package '{}' created".format(NO_SETTINGS_PACKAGE_ID), client.out)
        client.run('upload lib/1.0 -c --all -r default')
        assert "Uploading lib/1.0 to remote" in client.out

        # Verify that in the remote it is stored as "_"
        pref = PkgReference.loads("lib/1.0@#0:{}#0".format(NO_SETTINGS_PACKAGE_ID))
        path = server.server_store.export(pref.ref)
        self.assertIn("/lib/1.0/_/_/0/export", path.replace("\\", "/"))

        path = server.server_store.package(pref)
        self.assertIn("/lib/1.0/_/_/0/package", path.replace("\\", "/"))

        # Should be possible with explicit package
        client.run(f'upload lib/1.0:{NO_SETTINGS_PACKAGE_ID} -r default')
        self.assertIn(f"Uploading package 1/1: {NO_SETTINGS_PACKAGE_ID} to 'default'",
                      client.out)

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
                    elif "Hello0" in url and "1.2.1" in url and "v1" in url:
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
        files = {"conanfile.py": GenConanfile("Hello0", "1.2.1")}
        client.save(files)
        client.run("create . user/testing")
        client.run("remote logout '*'")
        client.run("upload Hello0/1.2.1@user/testing --all -r default")
        assert "Uploading Hello0/1.2.1@user/testing to remote" in client.out

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_upload_with_recipe_revision(self):
        ref = ConanFileReference.loads("pkg/1.0@user/channel")
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
        ref = ConanFileReference.loads("pkg/1.0@user/channel")
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
