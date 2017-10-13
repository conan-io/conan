import unittest

from conans.test.utils.tools import TestClient
from conans.test.utils.test_files import temp_folder
import os
from conans.model.manifest import FileTreeManifest
from conans.util.files import load


class DeployTest(unittest.TestCase):

    def deploy_test(self):
        client = TestClient()
        libconanfile = """from conans import ConanFile
from conans.tools import save
class Lib(ConanFile):
    exports_sources = "*"
    def build(self):
        save("mylib.dll", "mydll")
    def package(self):
        self.copy("*")
    def deploy(self):
        self.output.info("Lib deploy()")
"""
        client.save({"conanfile.py": libconanfile,
                     "License.md": "lib license",
                     "otherfile": ""})
        client.run("create Lib/0.1@user/testing")
        self.assertNotIn("Lib deploy()", client.out)

        conanfile = """from conans import ConanFile
from conans.tools import save
class Pkg(ConanFile):
    requires = "Lib/0.1@user/testing"
    def build(self):
        save("myapp.exe", "myexe")
    def package(self):
        self.copy("*")
    def deploy(self):
        self.output.info("Pkg deploy()")
        self.copy("*.exe")
        self.copy_deps("*.dll")
"""
        client.save({"conanfile.py": conanfile})
        client.run("create Pkg/0.1@user/testing")
        self.assertNotIn("deploy()", client.out)
        client.current_folder = temp_folder()
        client.run("install Pkg/0.1@user/testing")
        self.assertIn("Pkg/0.1@user/testing deploy(): Copied 1 '.dll' files: mylib.dll",
                      client.out)
        self.assertIn("Pkg/0.1@user/testing deploy(): Copied 1 '.exe' files: myapp.exe",
                      client.out)
        deploy_manifest = FileTreeManifest.loads(load(os.path.join(client.current_folder,
                                                                   "deploy_manifest.txt")))

        app = os.path.join(client.current_folder, "myapp.exe")
        lib = os.path.join(client.current_folder, "mylib.dll")
        self.assertEqual(sorted([app, lib]),
                         sorted(deploy_manifest.file_sums.keys()))
        self.assertEqual(load(app), "myexe")
        self.assertEqual(load(lib), "mydll")
