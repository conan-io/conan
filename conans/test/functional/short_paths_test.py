import os
import platform
import unittest

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient


class ShortPathsTest(unittest.TestCase):

    @unittest.skipUnless(platform.system() == "Windows", "Requires Windows")
    def short_paths_test(self):
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
        self.assertIn("source_file.cpp", os.listdir(source_folder))
        self.assertNotIn(".conan_link", os.listdir(source_folder))
        self.assertIn("BUILD: source_file.cpp", client.out)
        self.assertIn("BUILD: artifact", client.out)
        self.assertIn("source_file.cpp", os.listdir(build_folder))
        self.assertIn("artifact", os.listdir(build_folder))
        self.assertNotIn(".conan_link", os.listdir(build_folder))
        self.assertIn("PACKAGE: source_file.cpp", client.out)
        self.assertIn("PACKAGE: artifact", client.out)
        self.assertIn("source_file.cpp", os.listdir(package_folder))
        self.assertIn("artifact", os.listdir(package_folder))
        self.assertNotIn(".conan_link", os.listdir(package_folder))
        client.save({"conanfile.py": conanfile.format("True")})
        client.run("create . danimtb/testing")
        self.assertIn("SOURCE: source_file.cpp", client.out)
        self.assertNotIn("source_file.cpp", os.listdir(source_folder))
        self.assertIn(".conan_link", os.listdir(source_folder))
        self.assertIn("BUILD: source_file.cpp", client.out)
        self.assertIn("BUILD: artifact", client.out)
        self.assertNotIn("source_file.cpp", os.listdir(build_folder))
        self.assertNotIn("artifact", os.listdir(build_folder))
        self.assertIn(".conan_link", os.listdir(build_folder))
        self.assertIn("PACKAGE: source_file.cpp", client.out)
        self.assertIn("PACKAGE: artifact", client.out)
        self.assertNotIn("source_file.cpp", os.listdir(package_folder))
        self.assertNotIn("artifact", os.listdir(package_folder))
        self.assertIn(".conan_link", os.listdir(package_folder))
