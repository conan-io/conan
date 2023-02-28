import json
import os
import textwrap
import unittest

import pytest
from requests import ConnectionError

from conans.model.recipe_ref import RecipeReference
from conans.paths import CONAN_MANIFEST
from conans.test.utils.tools import (NO_SETTINGS_PACKAGE_ID, TestClient, TestRequester, TestServer,
                                     GenConanfile)
from conans.util.files import load, save


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
        assert "Uploading recipe 'hello%s/1.2.1@frodo/stable" % num in client.out

    client.run("upload hello0* --confirm -r default")
    assert f"'hello0/1.2.1@frodo/stable#761f54e34d59deb172d6078add7050a7' "\
           "already in server, skipping upload" in client.out
    assert "hello1" not in client.out
    assert "hello2" not in client.out


def test_check_upload_confirm_question():
    server = TestServer()
    client = TestClient(servers={"default": server}, inputs=["yes", "admin", "password", "n", "n"])
    client.save({"conanfile.py": GenConanfile("hello1", "1.2.1")})
    client.run("export . --user=frodo --channel=stable")
    client.run("upload hello* -r default")

    assert "Uploading recipe 'hello1/1.2.1@frodo/stable" in client.out

    client.save({"conanfile.py": GenConanfile("hello2", "1.2.1")})
    client.run("export . --user=frodo --channel=stable")
    client.run("upload hello* -r default")

    assert "Uploading recipe 'hello2/1.2.1@frodo/stable" not in client.out


class UploadTest(unittest.TestCase):

    def _get_client(self, requester=None):
        servers = {}
        # All can write (for avoid authentication until we mock user_io)
        self.test_server = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")],
                                      users={"lasote": "mypass"})
        servers["default"] = self.test_server
        test_client = TestClient(servers=servers, inputs=["lasote", "mypass"],
                                 requester_class=requester)
        return test_client

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
        self._set_global_conf(client, retry_wait=0)
        client.run("upload hello* --confirm -r default")
        self.assertIn("Can't connect because of the evil mock", client.out)
        self.assertIn("Waiting 0 seconds to retry...", client.out)

        # but not with 0
        client = self._get_client(BadConnectionUploader)
        files = {"conanfile.py": GenConanfile("hello0", "1.2.1").with_exports("*"),
                 "somefile.txt": ""}
        client.save(files)
        client.run("export . --user=frodo --channel=stable")
        self._set_global_conf(client, retry=0, retry_wait=1)
        client.run("upload hello* --confirm -r default", assert_error=True)
        self.assertNotIn("Waiting 1 seconds to retry...", client.out)
        self.assertIn("Execute upload again to retry upload the failed files: "
                      "conan_export.tgz. [Remote: default]", client.out)

        # Try with broken connection even with 10 retries
        client = self._get_client(TerribleConnectionUploader)
        files = {"conanfile.py": GenConanfile("hello0", "1.2.1").with_exports("*")}
        client.save(files)
        client.run("export . --user=frodo --channel=stable")
        self._set_global_conf(client, retry=10, retry_wait=0)
        client.run("upload hello* --confirm -r default", assert_error=True)
        self.assertIn("Waiting 0 seconds to retry...", client.out)
        self.assertIn("Execute upload again to retry upload the failed files", client.out)

        # For each file will fail the first time and will success in the second one
        client = self._get_client(FailPairFilesUploader)
        files = {"conanfile.py": GenConanfile("hello0", "1.2.1").with_exports("*")}
        client.save(files)
        client.run("export . --user=frodo --channel=stable")
        client.run("install --requires=hello0/1.2.1@frodo/stable --build='*' -r default")
        self._set_global_conf(client, retry=3, retry_wait=0)
        client.run("upload hello* --confirm -r default")
        self.assertEqual(str(client.out).count("ERROR: Pair file, error!"), 5)

    def _set_global_conf(self, client, retry=None, retry_wait=None):
        lines = []
        if retry is not None:
            lines.append("core.upload:retry={}".format(retry) )
        if retry_wait is not None:
            lines.append("core.upload:retry_wait={}".format(retry_wait))

        client.save({"global.conf": "\n".join(lines)}, path=client.cache.cache_folder)

    def test_upload_error_with_config(self):
        """Cause an error in the transfer and see some message"""

        # This will fail in the first put file, so, as we need to
        # upload 3 files (conanmanifest, conanfile and tgz) will do it with 2 retries
        client = self._get_client(BadConnectionUploader)
        files = {"conanfile.py": GenConanfile("hello0", "1.2.1").with_exports("*")}
        client.save(files)
        client.run("export . --user=frodo --channel=stable")
        self._set_global_conf(client, retry_wait=0)

        client.run("upload hello* --confirm -r default")
        self.assertIn("Can't connect because of the evil mock", client.out)
        self.assertIn("Waiting 0 seconds to retry...", client.out)

        # but not with 0
        client = self._get_client(BadConnectionUploader)
        files = {"conanfile.py": GenConanfile("hello0", "1.2.1").with_exports("*"),
                 "somefile.txt": ""}
        client.save(files)
        client.run("export . --user=frodo --channel=stable")

        self._set_global_conf(client, retry=0, retry_wait=1)
        client.run("upload hello* --confirm -r default", assert_error=True)
        self.assertNotIn("Waiting 1 seconds to retry...", client.out)
        self.assertIn("Execute upload again to retry upload the failed files: "
                      "conan_export.tgz. [Remote: default]", client.out)

        # Try with broken connection even with 10 retries
        client = self._get_client(TerribleConnectionUploader)
        files = {"conanfile.py": GenConanfile("hello0", "1.2.1").with_exports("*")}
        client.save(files)
        client.run("export . --user=frodo --channel=stable")
        self._set_global_conf(client, retry=10, retry_wait=0)
        client.run("upload hello* --confirm -r default", assert_error=True)
        self.assertIn("Waiting 0 seconds to retry...", client.out)
        self.assertIn("Execute upload again to retry upload the failed files", client.out)

        # For each file will fail the first time and will success in the second one
        client = self._get_client(FailPairFilesUploader)
        files = {"conanfile.py": GenConanfile("hello0", "1.2.1").with_exports("*")}
        client.save(files)
        client.run("export . --user=frodo --channel=stable")
        client.run("install --requires=hello0/1.2.1@frodo/stable --build='*'")
        self._set_global_conf(client, retry=3, retry_wait=0)
        client.run("upload hello* --confirm -r default")
        self.assertEqual(str(client.out).count("ERROR: Pair file, error!"), 5)

    def test_upload_same_package_dont_compress(self):
        client = self._get_client()
        client.save({"conanfile.py":GenConanfile().with_exports_sources("*"), "content.txt": "foo"})
        client.run("create . --name foo --version 1.0")

        client.run("upload foo/1.0 -r default")
        self.assertIn("Compressing recipe", client.out)
        self.assertIn("Compressing package", str(client.out))

        client.run("upload foo/1.0 -r default")
        self.assertNotIn("Compressing recipe", client.out)
        self.assertNotIn("Compressing package", str(client.out))
        self.assertIn("already in server, skipping upload", str(client.out))

    @pytest.mark.xfail(reason="No output json available yet for upload. Also old test, has to be "
                              "upgraded")
    def test_upload_json(self):
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.files import copy

            class TestConan(ConanFile):
                name = "test"
                version = "0.1"

                def package(self):
                    copy(self, "mylib.so", self.build_folder, os.path.join(self.package_folder, "lib"))
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
