import platform
import unittest

from nose.plugins.attrib import attr

from conans.model.ref import ConanFileReference
from conans.test.utils.test_files import hello_conan_files
from conans.test.utils.tools import TestClient, TestServer
from conans.client.tools.env import environment_append


@attr('golang')
class GoDiamondTest(unittest.TestCase):

    def setUp(self):
        test_server = TestServer()
        self.servers = {"default": test_server}
        self.conan = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})

    def _export_upload(self, ref_str, number=0, deps=None):
        ref = ConanFileReference.loads(ref_str)
        files = hello_conan_files(ref=ref, number=number, deps=deps,
                                  lang='go')
        self.conan.save(files, clean_first=True)
        self.conan.run("export . lasote/stable")
        self.conan.run("upload %s" % str(ref))

    def reuse_test(self):
        self._export_upload("hello0/0.1@lasote/stable")
        self._export_upload("hello1/0.1@lasote/stable", 1, [0])
        self._export_upload("hello2/0.1@lasote/stable", 2, [0])
        self._export_upload("hello3/0.1@lasote/stable", 3, [1, 2])

        client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        ref = ConanFileReference.loads("hello4/0.2@lasote/stable")
        files3 = hello_conan_files(ref=ref, number=4, deps=[3], lang='go')
        client.save(files3)
        client.run("install . --build missing")
        client.run("build .")

        with environment_append({"PATH": ['$GOPATH/bin'], 'GOPATH': client.current_folder}):
            with client.chdir("src"):
                client.run_command('go install hello4_main')
        if platform.system() == "Windows":
            command = "hello4_main"
        else:
            command = './hello4_main'
        with client.chdir("bin"):
            client.run_command(command)

        self.assertEqual(['Hello 4', 'Hello 3', 'Hello 1', 'Hello 0', 'Hello 2', 'Hello 0'],
                         str(client.out).splitlines()[-6:])

        # Try to upload and reuse the binaries
        client.run("upload hello3/0.1@lasote/stable --all")
        self.assertEqual(str(client.out).count("Uploading package"), 1)
        client.run("upload hello1/0.1@lasote/stable --all")
        self.assertEqual(str(client.out).count("Uploading package"), 1)
        client.run("upload hello2/0.1@lasote/stable --all")
        self.assertEqual(str(client.out).count("Uploading package"), 1)
        client.run("upload hello0/0.1@lasote/stable --all")
        self.assertEqual(str(client.out).count("Uploading package"), 1)
#
        client2 = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        ref = ConanFileReference.loads("hello4/0.2@lasote/stable")

        files3 = hello_conan_files(ref=ref, number=4, deps=[3], lang='go')
        client2.save(files3)

        client2.run("install . --build missing")
        with environment_append({"PATH": ['$GOPATH/bin'], 'GOPATH': client2.current_folder}):
            with client2.chdir("src"):
                client2.run_command('go install hello4_main')
        if platform.system() == "Windows":
            command = "hello4_main"
        else:
            command = './hello4_main'
        with client2.chdir("bin"):
            client2.run_command(command)

        self.assertEqual(['Hello 4', 'Hello 3', 'Hello 1', 'Hello 0', 'Hello 2', 'Hello 0'],
                         str(client2.out).splitlines()[-6:])
