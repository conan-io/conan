import os
import platform
import unittest

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient


class ShortPathsTest(unittest.TestCase):

    @unittest.skipUnless(platform.system() == "Windows", "Requires Windows")
    def inconsistent_cache_test(self):
        conanfile = """
import os
from conans import ConanFile, tools


class TestConan(ConanFile):
    name = "test"
    version = "1.0"
    short_paths = {0}
    exports_sources = "source_file.cpp"

    def source(self):
        for item in os.listdir(self.source_folder):
            self.output.info("SOURCE: " + str(item))
    def build(self):
        tools.save(os.path.join(self.build_folder, "artifact"), "")
        for item in os.listdir(self.build_folder):
            self.output.info("BUILD: " + str(item))
    def package(self):
        self.copy("source_file.cpp")
        self.copy("artifact")
        for item in os.listdir(self.build_folder):
            self.output.info("PACKAGE: " + str(item))
"""

        client = TestClient()
        client.save({"conanfile.py": conanfile.format("False"),
                     "source_file.cpp": ""})
        client.run("create . danimtb/testing")
        conan_ref = ConanFileReference("test", "1.0", "danimtb", "testing")
        source_folder = os.path.join(client.client_cache.conan(conan_ref), "source")
        build_folder = os.path.join(client.client_cache.conan(conan_ref), "build",
                                    "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        package_folder = os.path.join(client.client_cache.conan(conan_ref), "package",
                                      "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertIn("SOURCE: source_file.cpp", client.out)
        self.assertEqual(["source_file.cpp"], os.listdir(source_folder))
        self.assertIn("BUILD: source_file.cpp", client.out)
        self.assertIn("BUILD: artifact", client.out)
        self.assertEqual(
            sorted(["artifact", "conanbuildinfo.txt", "conaninfo.txt", "source_file.cpp"]),
            sorted(os.listdir(build_folder)))
        self.assertIn("PACKAGE: source_file.cpp", client.out)
        self.assertIn("PACKAGE: artifact", client.out)
        self.assertEqual(
            sorted(["artifact", "conaninfo.txt", "conanmanifest.txt", "source_file.cpp"]),
            sorted(os.listdir(package_folder)))
        client.save({"conanfile.py": conanfile.format("True")})
        client.run("create . danimtb/testing")
        self.assertIn("SOURCE: source_file.cpp", client.out)
        self.assertEqual([".conan_link"], os.listdir(source_folder))
        self.assertIn("BUILD: source_file.cpp", client.out)
        self.assertIn("BUILD: artifact", client.out)
        self.assertEqual([".conan_link"], os.listdir(build_folder))
        self.assertIn("PACKAGE: source_file.cpp", client.out)
        self.assertIn("PACKAGE: artifact", client.out)
        self.assertEqual([".conan_link"], os.listdir(package_folder))

    @unittest.skipUnless(platform.system() == "Windows", "Requires Windows")
    def package_output_test(self):
        conanfile = """
import os
from conans import ConanFile, tools


class TestConan(ConanFile):
    name = "test"
    version = "1.0"
    short_paths = True
"""
        client = TestClient()
        client.save({"conanfile.py": conanfile,
                     "source_file.cpp": ""})
        client.run("create . danimtb/testing")
        self.assertNotIn("test/1.0@danimtb/testing: Package '1' created", client.out)
        self.assertIn(
            "test/1.0@danimtb/testing: Package '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9' created",
            client.out)

        # try local flow still works, but no pkg id available
        client.run("install .")
        client.run("package .")
        self.assertIn("PROJECT: Package 'package' created", client.out)

        # try export-pkg with package folder
        client.run("remove test/1.0@danimtb/testing --force")
        client.run("export-pkg . test/1.0@danimtb/testing --package-folder package")
        self.assertIn(
            "test/1.0@danimtb/testing: Package '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9' created",
            client.out)

        # try export-pkg without package folder
        client.run("remove test/1.0@danimtb/testing --force")
        client.run("export-pkg . test/1.0@danimtb/testing --install-folder .")
        self.assertIn(
            "test/1.0@danimtb/testing: Package '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9' created",
            client.out)

        # try conan get
        client.run("get test/1.0@danimtb/testing . -p 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertIn("conaninfo.txt", client.out)
        self.assertIn("conanmanifest.txt", client.out)
