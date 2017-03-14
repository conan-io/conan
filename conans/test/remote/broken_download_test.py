import unittest
from conans.test.utils.tools import TestServer, TestClient
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.model.ref import ConanFileReference
import os
from conans.util.files import save


class BrokenDownloadTest(unittest.TestCase):

    def basic_test(self):
        server = TestServer()
        servers = {"default": server}
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        files = cpp_hello_conan_files()
        client.save(files)
        client.run("export lasote/stable")
        ref = ConanFileReference.loads("Hello/0.1@lasote/stable")
        self.assertTrue(os.path.exists(client.paths.export(ref)))
        client.run("upload Hello/0.1@lasote/stable")
        client.run("remove Hello/0.1@lasote/stable -f")
        self.assertFalse(os.path.exists(client.paths.export(ref)))
        path = server.test_server.file_manager.paths.export(ref)
        tgz = os.path.join(path, "conan_export.tgz")
        save(tgz, "contents")  # dummy content to break it, so the download decompress will fail
        client.run("install Hello/0.1@lasote/stable --build", ignore_error=True)
        self.assertIn("ERROR: Error while downloading/extracting files to", client.user_io.out)
        self.assertFalse(os.path.exists(client.paths.export(ref)))
