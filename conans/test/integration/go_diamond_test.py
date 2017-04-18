import unittest
from conans.test.utils.tools import TestServer, TestClient
from conans.model.ref import ConanFileReference
import platform
import os
from conans.test.utils.context_manager import CustomEnvPath
from conans.test.utils.test_files import hello_conan_files
from nose.plugins.attrib import attr


@attr('golang')
class GoDiamondTest(unittest.TestCase):

    def setUp(self):
        test_server = TestServer()
        self.servers = {"default": test_server}
        self.conan = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})

    def _export_upload(self, ref_str, number=0, deps=None):
        conan_reference = ConanFileReference.loads(ref_str)
        files = hello_conan_files(conan_reference=conan_reference, number=number, deps=deps,
                                  lang='go')
        self.conan.save(files, clean_first=True)
        self.conan.run("export lasote/stable")
        self.conan.run("upload %s" % str(conan_reference))

    def reuse_test(self):
        self._export_upload("hello0/0.1@lasote/stable")
        self._export_upload("hello1/0.1@lasote/stable", 1, [0])
        self._export_upload("hello2/0.1@lasote/stable", 2, [0])
        self._export_upload("hello3/0.1@lasote/stable", 3, [1, 2])

        client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        conan_reference = ConanFileReference.loads("hello4/0.2@lasote/stable")
        files3 = hello_conan_files(conan_reference=conan_reference, number=4, deps=[3], lang='go')
        client.save(files3)
        client.run("install --build missing")
        client.run("build")
        command = os.sep.join([".", "bin", "say_hello"])
        with CustomEnvPath(paths_to_add=['$GOPATH/bin'],
                           var_to_add=[('GOPATH', client.current_folder), ]):

            client.runner('go install hello4_main', cwd=os.path.join(client.current_folder, 'src'))
        if platform.system() == "Windows":
            command = "hello4_main"
        else:
            command = './hello4_main'
        client.runner(command, cwd=os.path.join(client.current_folder, 'bin'))

        self.assertEqual(['Hello 4', 'Hello 3', 'Hello 1', 'Hello 0', 'Hello 2', 'Hello 0'],
                         str(client.user_io.out).splitlines()[-6:])

        # Try to upload and reuse the binaries
        client.run("upload hello3/0.1@lasote/stable --all")
        self.assertEqual(str(client.user_io.out).count("Uploading package"), 1)
        client.run("upload hello1/0.1@lasote/stable --all")
        self.assertEqual(str(client.user_io.out).count("Uploading package"), 1)
        client.run("upload hello2/0.1@lasote/stable --all")
        self.assertEqual(str(client.user_io.out).count("Uploading package"), 1)
        client.run("upload hello0/0.1@lasote/stable --all")
        self.assertEqual(str(client.user_io.out).count("Uploading package"), 1)
#
        client2 = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        conan_reference = ConanFileReference.loads("hello4/0.2@lasote/stable")

        files3 = hello_conan_files(conan_reference=conan_reference, number=4, deps=[3], lang='go')
        client2.save(files3)

        client2.run("install --build missing")
        command = os.sep.join([".", "bin", "say_hello"])
        with CustomEnvPath(paths_to_add=['$GOPATH/bin'],
                           var_to_add=[('GOPATH', client2.current_folder), ]):
            client2.runner('go install hello4_main',
                           cwd=os.path.join(client2.current_folder, 'src'))
        if platform.system() == "Windows":
            command = "hello4_main"
        else:
            command = './hello4_main'
        client2.runner(command, cwd=os.path.join(client2.current_folder, 'bin'))

        self.assertEqual(['Hello 4', 'Hello 3', 'Hello 1', 'Hello 0', 'Hello 2', 'Hello 0'],
                         str(client2.user_io.out).splitlines()[-6:])
