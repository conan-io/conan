import os
import unittest

from requests import ConnectionError

from conan.internal.paths import CONAN_MANIFEST
from conan.test.utils.tools import (TestClient, TestRequester, TestServer,
                                     GenConanfile)
from conan.test.utils.env import environment_update


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
    layout = client.exported_layout()
    os.unlink(os.path.join(layout.export(), CONAN_MANIFEST))
    client.run("upload %s -r default" % str(layout.reference), assert_error=True)
    assert "Cannot upload corrupted recipe" in client.out


def test_upload_with_pattern():
    client = TestClient(default_server_user=True)
    for num in range(3):
        client.save({"conanfile.py": GenConanfile("hello{}".format(num), "1.2.1")})
        client.run("export . --user=frodo --channel=stable")

    client.run("upload hello* --confirm -r default")
    print(client.out)
    for num in range(3):
        assert "Uploading recipe 'hello%s/1.2.1@frodo/stable" % num in client.out

    client.run("upload hello0* --confirm -r default")
    assert f"'hello0/1.2.1@frodo/stable#761f54e34d59deb172d6078add7050a7' "\
           "already in server, skipping upload" in client.out
    assert "hello1" not in client.out
    assert "hello2" not in client.out


def test_check_upload_confirm_question():
    server = TestServer()
    client = TestClient(servers={"default": server},
                        inputs=["yes", "admin", "password", "n", "n", "n"])
    client.save({"conanfile.py": GenConanfile("hello1", "1.2.1")})
    client.run("export . --user=frodo --channel=stable")
    client.run("upload hello* -r default")

    assert "Uploading recipe 'hello1/1.2.1@frodo/stable" in client.out

    client.save({"conanfile.py": GenConanfile("hello2", "1.2.1")})
    client.run("create . --user=frodo --channel=stable")
    client.run("upload hello* -r default")

    assert "Uploading recipe 'hello2/1.2.1@frodo/stable" not in client.out


def test_check_upload_confirm_question_yes():
    server = TestServer()
    client = TestClient(servers={"default": server},
                        inputs=["yes", "yes", "yes", "yes", "yes", "admin", "password"])
    client.save({"conanfile.py": GenConanfile("hello1", "1.2.1")})
    client.run("create . ")
    client.save({"conanfile.py": GenConanfile("hello1", "1.2.1").with_package_file("file.txt",
                                                                                   env_var="MYVAR")})

    with environment_update({"MYVAR": "0"}):
        client.run("create . ")
    with environment_update({"MYVAR": "1"}):
        client.run("create . ")
    client.run("upload hello*#*:*#* -r default")
    assert str(client.out).count("(Uploaded)") == 5


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
        self.assertEqual(str(client.out).count("WARN: network: Pair file, error!"), 5)

    def _set_global_conf(self, client, retry=None, retry_wait=None):
        lines = []
        if retry is not None:
            lines.append("core.upload:retry={}".format(retry) )
        if retry_wait is not None:
            lines.append("core.upload:retry_wait={}".format(retry_wait))

        client.save_home({"global.conf": "\n".join(lines)})

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
        self.assertEqual(str(client.out).count("WARN: network: Pair file, error!"), 5)

    def test_upload_same_package_dont_compress(self):
        client = self._get_client()
        client.save({"conanfile.py":GenConanfile().with_exports_sources("*"), "content.txt": "foo"})
        client.run("create . --name foo --version 1.0")

        client.run("upload foo/1.0 -r default")
        self.assertIn("foo/1.0: Compressing conan_sources.tgz", client.out)
        self.assertIn("foo/1.0:da39a3ee5e6b4b0d3255bfef95601890afd80709: "
                      "Compressing conan_package.tgz", client.out)

        client.run("upload foo/1.0 -r default")
        self.assertNotIn("Compressing", client.out)
        self.assertIn("already in server, skipping upload", client.out)
