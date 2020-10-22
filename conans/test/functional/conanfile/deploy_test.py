import os
import unittest

from parameterized.parameterized import parameterized

from conans.model.manifest import FileTreeManifest
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient
from conans.util.files import load, mkdir


class DeployTest(unittest.TestCase):

    @parameterized.expand([(True, ), (False, )])
    def test_deploy(self, deploy_to_abs):
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
        client.run("create . Lib/0.1@user/testing")
        self.assertNotIn("Lib deploy()", client.out)

        if deploy_to_abs:
            dll_folder = temp_folder()
            mkdir(dll_folder)
        else:
            dll_folder = ""
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
        self.copy_deps("*.dll", dst="%s")
""" % dll_folder.replace("\\", "/")
        client.save({"conanfile.py": conanfile})
        client.run("create . Pkg/0.1@user/testing")
        self.assertNotIn("deploy()", client.out)

        def test_install_in(folder):
            client.current_folder = temp_folder()
            client.run("install Pkg/0.1@user/testing --install-folder=%s" % folder)

            self.assertIn("Pkg/0.1@user/testing deploy(): Copied 1 '.dll' file: mylib.dll",
                          client.out)
            self.assertIn("Pkg/0.1@user/testing deploy(): Copied 1 '.exe' file: myapp.exe",
                          client.out)
            deploy_manifest = FileTreeManifest.loads(
                    client.load(os.path.join(folder, "deploy_manifest.txt")))

            app = os.path.abspath(os.path.join(client.current_folder, folder, "myapp.exe"))
            if deploy_to_abs:
                lib = os.path.join(dll_folder, "mylib.dll")
            else:
                lib = os.path.abspath(os.path.join(client.current_folder, folder, "mylib.dll"))
            self.assertEqual(sorted([app, lib]),
                             sorted(deploy_manifest.file_sums.keys()))
            self.assertEqual(load(app), "myexe")
            self.assertEqual(load(lib), "mydll")

        test_install_in("./")
        test_install_in("other_install_folder")
