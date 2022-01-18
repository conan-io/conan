import json
import os
import platform
import stat
import textwrap
import unittest

import pytest
from requests import ConnectionError

from conans.client.tools.files import untargz
from conans.model.manifest import FileTreeManifest
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.paths import CONANFILE, CONANINFO, CONAN_MANIFEST, EXPORT_TGZ_NAME
from conans.test.utils.test_files import temp_folder, uncompress_packaged_files
from conans.test.utils.tools import (NO_SETTINGS_PACKAGE_ID, TestClient, TestRequester, TestServer,
                                     GenConanfile)
from conans.util.files import load, mkdir, save


class BadConnectionUploader(TestRequester):
    fail_on = 1

    def __init__(self, *args, **kwargs):
        super(BadConnectionUploader, self).__init__(*args, **kwargs)
        self.counter_fail = 0

    def put(self, *args, **kwargs):
        self.counter_fail += 1
        if self.counter_fail == self.fail_on:
            raise ConnectionError("Can't connect because of the evil mock")
        else:
            return super(BadConnectionUploader, self).put(*args, **kwargs)


class TerribleConnectionUploader(BadConnectionUploader):
    def put(self, *args, **kwargs):
        raise ConnectionError("Can't connect because of the evil mock")


class FailPairFilesUploader(BadConnectionUploader):

    def put(self, *args, **kwargs):
        self.counter_fail += 1
        if self.counter_fail % 2 == 1:
            raise ConnectionError("Pair file, error!")
        else:
            return super(BadConnectionUploader, self).put(*args, **kwargs)


def test_try_upload_bad_recipe():
    client = TestClient(default_server_user=True)
    client.save({"conanfile.py": GenConanfile("hello0", "1.2.1")})
    client.run("export . --user=frodo --channel=stable")
    ref = RecipeReference.loads("hello0/1.2.1@frodo/stable")
    latest_rrev = client.cache.get_latest_recipe_reference(ref)
    os.unlink(os.path.join(client.cache.ref_layout(latest_rrev).export(), CONAN_MANIFEST))
    client.run("upload %s -r default" % str(ref), assert_error=True)
    assert "Cannot upload corrupted recipe" in client.out


def test_upload_with_pattern():
    client = TestClient(default_server_user=True)
    for num in range(3):
        client.save({"conanfile.py": GenConanfile("hello{}".format(num), "1.2.1")})
        client.run("export . --user=frodo --channel=stable")

    client.run("upload hello* --confirm -r default")
    for num in range(3):
        assert "Uploading hello%s/1.2.1@frodo/stable" % num in client.out

    client.run("upload hello0* --confirm -r default")
    assert "hello0/1.2.1@frodo/stable#e895a89b63c4eb2055704f63e6a0d06f "\
           "already in server, skipping upload" in client.out
    assert "hello1" not in client.out
    assert "hello2" not in client.out


def test_check_upload_confirm_question():
    server = TestServer()
    client = TestClient(servers={"default": server}, inputs=["yes", "admin", "password", "n", "n"])
    client.save({"conanfile.py": GenConanfile("hello1", "1.2.1")})
    client.run("export . --user=frodo --channel=stable")
    client.run("upload hello* -r default")

    assert "Uploading hello1/1.2.1@frodo/stable" in client.out

    client.save({"conanfile.py": GenConanfile("hello2", "1.2.1")})
    client.run("export . --user=frodo --channel=stable")
    client.run("upload hello* -r default")

    assert "Uploading hello2/1.2.1@frodo/stable" not in client.out


@pytest.mark.xfail(reason="cache2.0: adapt these tests in the future")
class UploadTest(unittest.TestCase):

    def _get_client(self, requester=None):
        servers = {}
        # All can write (for avoid authentication until we mock user_io)
        self.test_server = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")],
                                      users={"lasote": "mypass"})
        servers["default"] = self.test_server
        test_client = TestClient(servers=servers, inputs=["lasote", "mypass"],
                                 requester_class=requester)
        save(test_client.cache.default_profile_path, "")
        return test_client

    def setUp(self):
        self.client = self._get_client()
        self.ref = RecipeReference.loads("hello/1.2.1@frodo/stable#myreciperev")
        self.pref = PkgReference(self.ref, "myfakeid", "mypackagerev")
        reg_folder = self.client.get_latest_ref_layout(self.ref).export()

        self.client.run('upload %s -r default' % str(self.ref), assert_error=True)
        self.assertIn("ERROR: Recipe not found: '%s'" % str(self.ref), self.client.out)

        files = {}
        self.client.save(files, path=reg_folder)
        self.client.save({CONANFILE: GenConanfile().with_name("hello").with_version("1.2.1"),
                          "include/math/lib1.h": "//copy",
                          "my_lib/debug/libd.a": "//copy",
                          "my_data/readme.txt": "//copy",
                          "my_bin/executable": "//copy"}, path=reg_folder)
        mkdir(self.client.get_latest_ref_layout(self.ref).export_sources())
        manifest = FileTreeManifest.create(reg_folder)
        manifest.time = '123123123'
        manifest.save(reg_folder)
        self.test_server.server_store.update_last_revision(self.ref)

        self.server_pack_folder = self.test_server.server_store.package(self.pref)

        package_folder = self.client.get_latest_pkg_layout(self.pref).package()
        save(os.path.join(package_folder, "include", "lib1.h"), "//header")
        save(os.path.join(package_folder, "lib", "my_lib", "libd.a"), "//lib")
        save(os.path.join(package_folder, "res", "shares", "readme.txt"),
             "//res")
        save(os.path.join(package_folder, "bin", "my_bin", "executable"), "//bin")
        save(os.path.join(package_folder, CONANINFO),
             """[recipe_hash]\n%s""" % manifest.summary_hash)
        FileTreeManifest.create(package_folder).save(package_folder)
        self.test_server.server_store.update_last_package_revision(self.pref)

        os.chmod(os.path.join(package_folder, "bin", "my_bin", "executable"),
                 os.stat(os.path.join(package_folder, "bin", "my_bin", "executable")).st_mode |
                 stat.S_IRWXU)

        expected_manifest = FileTreeManifest.create(package_folder)
        expected_manifest.save(package_folder)

        self.server_reg_folder = self.test_server.server_store.export(self.ref)
        self.assertFalse(os.path.exists(self.server_reg_folder))
        self.assertFalse(os.path.exists(self.server_pack_folder))

    def test_upload_error(self):
        """Cause an error in the transfer and see some message"""

        # Check for the default behaviour
        client = self._get_client(BadConnectionUploader)
        files = {"conanfile.py": GenConanfile("hello0", "1.2.1").with_exports("*")}
        client.save(files)
        client.run("export . --user=frodo --channel=stable")
        client.run("upload hello* --confirm -r default")
        self.assertIn("Can't connect because of the evil mock", client.out)
        self.assertIn("Waiting 5 seconds to retry...", client.out)

        # This will fail in the first put file, so, as we need to
        # upload 3 files (conanmanifest, conanfile and tgz) will do it with 2 retries
        client = self._get_client(BadConnectionUploader)
        files = {"conanfile.py": GenConanfile("hello0", "1.2.1").with_exports("*")}
        client.save(files)
        client.run("export . --user=frodo --channel=stable")
        client.run("upload hello* --confirm --retry-wait=0 -r default")
        self.assertIn("Can't connect because of the evil mock", client.out)
        self.assertIn("Waiting 0 seconds to retry...", client.out)

        # but not with 0
        client = self._get_client(BadConnectionUploader)
        files = {"conanfile.py": GenConanfile("hello0", "1.2.1").with_exports("*"),
                 "somefile.txt": ""}
        client.save(files)
        client.run("export . --user=frodo --channel=stable")
        client.run("upload hello* --confirm --retry 0 --retry-wait=1 -r default", assert_error=True)
        self.assertNotIn("Waiting 1 seconds to retry...", client.out)
        self.assertIn("ERROR: hello0/1.2.1@frodo/stable: Upload recipe to 'default' failed: "
                      "Execute upload again to retry upload the failed files: "
                      "conan_export.tgz. [Remote: default]", client.out)

        # Try with broken connection even with 10 retries
        client = self._get_client(TerribleConnectionUploader)
        files = {"conanfile.py": GenConanfile("hello0", "1.2.1").with_exports("*")}
        client.save(files)
        client.run("export . --user=frodo --channel=stable")
        client.run("upload hello* --confirm --retry 10 --retry-wait=0 -r default", assert_error=True)
        self.assertIn("Waiting 0 seconds to retry...", client.out)
        self.assertIn("ERROR: hello0/1.2.1@frodo/stable: Upload recipe to 'default' failed: "
                      "Execute upload again to retry upload the failed files", client.out)

        # For each file will fail the first time and will success in the second one
        client = self._get_client(FailPairFilesUploader)
        files = {"conanfile.py": GenConanfile("hello0", "1.2.1").with_exports("*")}
        client.save(files)
        client.run("export . --user=frodo --channel=stable")
        client.run("install --reference=hello0/1.2.1@frodo/stable --build -r default")
        client.run("upload hello* --confirm --retry 3 --retry-wait=0")
        self.assertEqual(str(client.out).count("ERROR: Pair file, error!"), 5)

    def test_upload_error_with_config(self):
        """Cause an error in the transfer and see some message"""

        # This will fail in the first put file, so, as we need to
        # upload 3 files (conanmanifest, conanfile and tgz) will do it with 2 retries
        client = self._get_client(BadConnectionUploader)
        files = {"conanfile.py": GenConanfile("hello0", "1.2.1").with_exports("*")}
        client.save(files)
        client.run("export . --user=frodo --channel=stable")
        conan_conf = textwrap.dedent("""
                                    [storage]
                                    path = ./data
                                    [general]
                                    retry_wait=0
                                """)
        client.save({"conan.conf": conan_conf}, path=client.cache.cache_folder)

        client.run("upload hello* --confirm")
        self.assertIn("Can't connect because of the evil mock", client.out)
        self.assertIn("Waiting 0 seconds to retry...", client.out)

        # but not with 0
        client = self._get_client(BadConnectionUploader)
        files = {"conanfile.py": GenConanfile("hello0", "1.2.1").with_exports("*"),
                 "somefile.txt": ""}
        client.save(files)
        client.run("export . --user=frodo --channel=stable")

        conan_conf = textwrap.dedent("""
                                    [storage]
                                    path = ./data
                                    [general]
                                    retry=0
                                    retry_wait=1
                                """)
        client.save({"conan.conf": conan_conf}, path=client.cache.cache_folder)
        client.run("upload hello* --confirm -r default", assert_error=True)
        self.assertNotIn("Waiting 1 seconds to retry...", client.out)
        self.assertIn("ERROR: hello0/1.2.1@frodo/stable: Upload recipe to 'default' failed: "
                      "Execute upload again to retry upload the failed files: "
                      "conan_export.tgz. [Remote: default]", client.out)

        # Try with broken connection even with 10 retries
        client = self._get_client(TerribleConnectionUploader)
        files = {"conanfile.py": GenConanfile("hello0", "1.2.1").with_exports("*")}
        client.save(files)
        client.run("export . --user=frodo --channel=stable")
        conan_conf = textwrap.dedent("""
                                    [storage]
                                    path = ./data
                                    [general]
                                    retry=10
                                    retry_wait=0
                                """)
        client.save({"conan.conf": conan_conf}, path=client.cache.cache_folder)
        client.run("upload hello* --confirm -r default", assert_error=True)
        self.assertIn("Waiting 0 seconds to retry...", client.out)
        self.assertIn("ERROR: hello0/1.2.1@frodo/stable: Upload recipe to 'default' failed: "
                      "Execute upload again to retry upload the failed files", client.out)

        # For each file will fail the first time and will success in the second one
        client = self._get_client(FailPairFilesUploader)
        files = {"conanfile.py": GenConanfile("hello0", "1.2.1").with_exports("*")}
        client.save(files)
        client.run("export . --user=frodo --channel=stable")
        client.run("install --reference=hello0/1.2.1@frodo/stable --build")
        conan_conf = textwrap.dedent("""
                                    [storage]
                                    path = ./data
                                    [general]
                                    retry=3
                                    retry_wait=0
                                """)
        client.save({"conan.conf": conan_conf}, path=client.cache.cache_folder)
        client.run("upload hello* --confirm")
        self.assertEqual(str(client.out).count("ERROR: Pair file, error!"), 5)

    def test_upload_same_package_dont_compress(self):
        # Create a manifest for the faked package
        package_path = self.client.get_latest_pkg_layout(self.pref).package()
        expected_manifest = FileTreeManifest.create(package_path)
        expected_manifest.save(package_path)

        self.client.run("upload %s" % str(self.ref))
        self.assertIn("Compressing recipe", self.client.out)
        self.assertIn("Compressing package", str(self.client.out))

        self.client.run("upload %s" % str(self.ref))
        self.assertNotIn("Compressing recipe", self.client.out)
        self.assertNotIn("Compressing package", str(self.client.out))
        self.assertIn("Package is up to date", str(self.client.out))

    def test_upload_with_no_valid_settings(self):
        # Check if upload is still working even if the specified setting is not valid.
        # If this test fails, will fail in Linux/OSx
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class TestConan(ConanFile):
                name = "hello"
                version = "1.2"
                settings = "os"
            """)
        self.client.save({CONANFILE: conanfile})
        self.client.run("export . --user=lasote --channel=stable")
        self.client.run("upload hello/1.2@lasote/stable")
        self.assertIn("Uploading conanmanifest.txt", self.client.out)

    def test_single_binary(self):
        # Try to upload an package without upload conans first
        self.client.run('upload %s -p %s -r default' % (self.ref, str(self.pref.package_id)))
        self.assertIn("Uploading %s to remote" % str(self.ref), self.client.out)

    def test_simple(self):
        # Upload package
        self.client.run('upload %s -r default' % str(self.ref))
        self.server_reg_folder = self.test_server.server_store.export(self.ref)

        self.assertTrue(os.path.exists(self.server_reg_folder))

        # Upload package
        self.client.run('upload %s -p %s -r default' % (str(self.ref), str(self.pref.package_id)))

        self.server_pack_folder = self.test_server.server_store.package(self.pref)

        self.assertTrue(os.path.exists(self.server_reg_folder))
        self.assertTrue(os.path.exists(self.server_pack_folder))

        # Test the file in the downloaded conans
        files = ['my_lib/debug/libd.a',
                 CONANFILE,
                 CONAN_MANIFEST,
                 'include/math/lib1.h',
                 'my_data/readme.txt',
                 'my_bin/executable']

        self.assertTrue(os.path.exists(os.path.join(self.server_reg_folder, CONANFILE)))
        self.assertTrue(os.path.exists(os.path.join(self.server_reg_folder, EXPORT_TGZ_NAME)))
        tmp = temp_folder()
        untargz(os.path.join(self.server_reg_folder, EXPORT_TGZ_NAME), tmp)
        for f in files:
            if f not in (CONANFILE, CONAN_MANIFEST):
                self.assertTrue(os.path.exists(os.path.join(tmp, f)))
            else:
                self.assertFalse(os.path.exists(os.path.join(tmp, f)))

        folder = uncompress_packaged_files(self.test_server.server_store, self.pref)

        self.assertTrue(os.path.exists(os.path.join(folder, "include", "lib1.h")))
        self.assertTrue(os.path.exists(os.path.join(folder, "lib", "my_lib/libd.a")))
        self.assertTrue(os.path.exists(os.path.join(folder, "res", "shares/readme.txt")))

        if platform.system() != "Windows":
            self.assertEqual(os.stat(os.path.join(folder, "bin", "my_bin/executable")).st_mode &
                             stat.S_IRWXU, stat.S_IRWXU)

    def test_upload_all(self):
        """Upload recipe and package together"""
        # Try to upload all conans and packages
        self.client.run('user -p mypass -r default lasote')
        self.client.run('upload %s -r default' % str(self.ref))
        lines = [line.strip() for line in str(self.client.out).splitlines()
                 if line.startswith("Uploading")]
        self.assertEqual(lines, ["Uploading to remote 'default':",
                                 "Uploading hello/1.2.1@frodo/stable to remote 'default'",
                                 "Uploading conan_export.tgz -> hello/1.2.1@frodo/stable",
                                 "Uploading conanfile.py -> hello/1.2.1@frodo/stable",
                                 "Uploading conanmanifest.txt -> hello/1.2.1@frodo/stable",
                                 "Uploading package 1/1: myfakeid to 'default'",
                                 "Uploading conan_package.tgz -> hello/1.2.1@frodo/stable:myfa",
                                 "Uploading conaninfo.txt -> hello/1.2.1@frodo/stable:myfa",
                                 "Uploading conanmanifest.txt -> hello/1.2.1@frodo/stable:myfa",
                                 ])

        rev = self.client.cache.get_latest_recipe_reference(self.ref).revision
        prev = self.client.cache.get_latest_package_reference(self.ref).revision
        self.ref.revision = rev

        self.pref.revision = prev
        server_reg_folder = self.test_server.server_store.export(self.ref)
        server_pack_folder = self.test_server.server_store.package(self.pref)

        self.assertTrue(os.path.exists(server_reg_folder))
        self.assertTrue(os.path.exists(server_pack_folder))

    def test_force(self):
        # Tries to upload a package exported after than remote version.
        # Upload all recipes and packages
        self.client.run('upload %s -r default' % str(self.ref))

        rev = self.client.cache.get_latest_recipe_reference(self.ref).revision
        prev = self.client.cache.get_latest_package_reference(self.ref).revision
        self.ref.revision = rev
        self.pref.revision = prev

        self.server_reg_folder = self.test_server.server_store.export(self.ref)
        self.server_pack_folder = self.test_server.server_store.package(self.pref)

        self.assertTrue(os.path.exists(self.server_reg_folder))
        self.assertTrue(os.path.exists(self.server_pack_folder))

        # Fake datetime from exported date and upload again

        old_digest = self.client.get_latest_ref_layout(self.ref).recipe_manifest()
        old_digest.file_sums["new_file"] = "012345"
        fake_digest = FileTreeManifest(2, old_digest.file_sums)
        fake_digest.save(self.client.get_latest_ref_layout(self.ref).export())

        self.client.run('upload %s -r default' % str(self.ref), assert_error=True)
        self.assertIn("Remote recipe is newer than local recipe", self.client.out)

        self.client.run('upload %s --force -r default' % str(self.ref))
        self.assertIn("Uploading %s" % str(self.ref),
                      self.client.out)

        # Repeat transfer, to make sure it is uploading again
        self.client.run('upload %s --force -r default' % str(self.ref))
        self.assertIn("Uploading conan_export.tgz", self.client.out)
        self.assertIn("Uploading conanfile.py", self.client.out)

    def test_upload_json(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class TestConan(ConanFile):
                name = "test"
                version = "0.1"

                def package(self):
                    self.copy("mylib.so", dst="lib")
            """)

        client = self._get_client()
        client.save({"conanfile.py": conanfile,
                     "mylib.so": ""})
        client.run("create . danimtb/testing")

        # Test conflict parameter error
        client.run("upload test/0.1@danimtb/* -p ewvfw --json upload.json", assert_error=True)

        json_path = os.path.join(client.current_folder, "upload.json")
        self.assertTrue(os.path.exists(json_path))
        json_content = load(json_path)
        output = json.loads(json_content)
        self.assertTrue(output["error"])
        self.assertEqual(0, len(output["uploaded"]))

        # Test invalid reference error
        client.run("upload fake/0.1@danimtb/testing --json upload.json", assert_error=True)
        json_path = os.path.join(client.current_folder, "upload.json")
        self.assertTrue(os.path.exists(json_path))
        json_content = load(json_path)
        output = json.loads(json_content)
        self.assertTrue(output["error"])
        self.assertEqual(0, len(output["uploaded"]))

        # Test normal upload
        client.run("upload test/0.1@danimtb/testing --json upload.json")
        self.assertTrue(os.path.exists(json_path))
        json_content = load(json_path)
        output = json.loads(json_content)
        output_expected = {"error": False,
                           "uploaded": [
                               {
                                   "recipe": {
                                       "id": "test/0.1@danimtb/testing",
                                       "remote_url": "unknown",
                                       "remote_name": "default",
                                       "time": "unknown"
                                   },
                                   "packages": [
                                       {
                                           "id": NO_SETTINGS_PACKAGE_ID,
                                           "time": "unknown"
                                       }
                                   ]
                               }
                           ]}
        self.assertEqual(output_expected["error"], output["error"])
        self.assertEqual(len(output_expected["uploaded"]), len(output["uploaded"]))

        for i, item in enumerate(output["uploaded"]):
            self.assertEqual(output_expected["uploaded"][i]["recipe"]["id"], item["recipe"]["id"])
            self.assertEqual(output_expected["uploaded"][i]["recipe"]["remote_name"],
                             item["recipe"]["remote_name"])
            for j, subitem in enumerate(item["packages"]):
                self.assertEqual(output_expected["uploaded"][i]["packages"][j]["id"],
                                 subitem["id"])
