import unittest
import os

from conans.model.ref import PackageReference, ConanFileReference
from conans.test.utils.tools import TestServer, TestClient, NO_SETTINGS_PACKAGE_ID


conanfile = """
import os
from conans import ConanFile
class Pkg(ConanFile):

    def build(self):
        with open(os.path.join(self.build_folder, "build_file.txt"), "w") as f:
            f.write("Build file")

    def package(self):
        with open(os.path.join(self.package_folder, "package_file.txt"), "w") as f:
            f.write("Packaged file")

    def package_install(self):
        self.output.warn("PACKAGE INSTALL CALL:{}".format(self.package_install_folder))
        with open(os.path.join(self.package_install_folder, "install_file.txt"), "w") as f:
            f.write("Installed file")

"""


class PackageInstallTest(unittest.TestCase):

    def setUp(self):
        self.server = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")])
        self.client = TestClient(servers={"default": self.server})
        self.client.run("config set general.package_install_folder=1")
        self.ref = ConanFileReference.loads("lib/1.0@")
        pid = PackageReference(self.ref, NO_SETTINGS_PACKAGE_ID)
        self.install_folder = self.client.cache.package_layout(self.ref).package_install(pid)
        self.package_folder = self.client.cache.package_layout(self.ref).package(pid)

    def conan_create_test(self):
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . {}@".format(self.ref))

        self.assertIn("PACKAGE INSTALL CALL:{}".format(self.install_folder), self.client.out)
        self.assertIn("package_file.txt", os.listdir(self.install_folder))
        self.assertIn("install_file.txt", os.listdir(self.install_folder))

        self.assertIn("package_file.txt", os.listdir(self.package_folder))
        self.assertNotIn("install_file.txt", os.listdir(self.package_folder))

    def conan_install_test(self):
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . {}@".format(self.ref))
        self.client.run('upload "*" -c --all')
        self.client.run('remove "*" -f')

        self.client.run("install {}@".format(self.ref))

        self.assertIn("PACKAGE INSTALL CALL:{}".format(self.install_folder), self.client.out)
        self.assertIn("package_file.txt", os.listdir(self.install_folder))
        self.assertIn("install_file.txt", os.listdir(self.install_folder))

        # Only tgz in the package folder
        self.assertIn("conan_package.tgz", os.listdir(self.package_folder))
        self.assertIn("conaninfo.txt", os.listdir(self.package_folder))
        self.assertIn("conanmanifest.txt", os.listdir(self.package_folder))
        self.assertNotIn("package_file.txt", os.listdir(self.package_folder))
        self.assertNotIn("install_file.txt", os.listdir(self.package_folder))

        # Build again the package, but now it will package "package_file2.txt" and will
        # install only install_file2.txt
        cf = conanfile.replace("package_file",
                               "package_file2").replace("install_file", "install_file2")
        self.client.save({"conanfile.py": cf})
        self.client.run("create . {}@".format(self.ref))

        self.assertNotIn("conan_package.tgz", os.listdir(self.package_folder))
        self.assertNotIn("package_file.txt", os.listdir(self.package_folder))
        self.assertNotIn("install_file.txt", os.listdir(self.package_folder))
        self.assertIn("package_file2.txt", os.listdir(self.package_folder))
        self.assertNotIn("install_file.txt", os.listdir(self.package_folder))

        self.assertNotIn("conan_package.tgz", os.listdir(self.install_folder))
        self.assertNotIn("package_file.txt", os.listdir(self.install_folder))
        self.assertNotIn("install_file.txt", os.listdir(self.install_folder))
        self.assertIn("package_file2.txt", os.listdir(self.install_folder))
        self.assertNotIn("install_file.txt", os.listdir(self.install_folder))
        self.assertIn("install_file2.txt", os.listdir(self.install_folder))

    def export_pkg_test(self):
        self.client.save({"conanfile.py": conanfile})
        self.client.run("install .")
        self.client.run("build . ")

        self.client.run("export-pkg . {}@ --build-folder=. --source-folder=.".format(self.ref))
        self.assertIn("package_file.txt", os.listdir(self.install_folder))
        self.assertIn("install_file.txt", os.listdir(self.install_folder))

        self.client.run('remove "*" -f')
        # It copies the files from current dir without calling package()
        self.client.run("export-pkg . {}@ --package-folder=.".format(self.ref))
        # TODO: Confirm! Should it call package_install when copying package directly??
        self.assertNotIn("package_file.txt", os.listdir(self.install_folder))
        self.assertIn("install_file.txt", os.listdir(self.install_folder))

    # TODO: Short paths test
