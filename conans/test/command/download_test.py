import unittest
import os
from conans.test.utils.tools import TestClient, TestServer
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.model.ref import ConanFileReference


class DownloadTest(unittest.TestCase):

    def download_reference_without_packages_test(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    settings = "os"
"""
        client.save({"conanfile.py": conanfile})

        server = TestServer()
        servers = {"default": server}

        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})

        files = cpp_hello_conan_files()
        client.save(files)

        client.run("export . lasote/stable")
        ref = ConanFileReference.loads("Hello/0.1@lasote/stable")
        self.assertTrue(os.path.exists(client.paths.conanfile(ref)))

        client.run("upload Hello/0.1@lasote/stable")
        client.run("remove Hello/0.1@lasote/stable -f")
        self.assertFalse(os.path.exists(client.paths.export(ref)))

        client.run("download Hello/0.1@lasote/stable", ignore_error=True)
        # Check 'No remote binary packages found' warning
        self.assertIn("WARN: No remote binary packages found in remote", client.out)
        # Check at least conanfile.py is downloaded
        self.assertTrue(os.path.exists(client.paths.conanfile(ref)))
