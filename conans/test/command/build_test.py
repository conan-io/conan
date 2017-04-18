from conans.test.utils.tools import TestClient
import unittest
from conans.paths import CONANFILE
from conans.model.ref import PackageReference


conanfile_scope_env = """
from conans import ConanFile

class AConan(ConanFile):
    requires = "Hello/0.1@lasote/testing"
    generators = "txt"

    def build(self):
        self.output.info("INCLUDE PATH: %s" % self.deps_cpp_info.include_paths[0])
        self.output.info("HELLO ROOT PATH: %s" % self.deps_cpp_info["Hello"].rootpath)
        self.output.info("HELLO INCLUDE PATHS: %s" % self.deps_cpp_info["Hello"].include_paths[0])
"""

conanfile_dep = """
from conans import ConanFile

class AConan(ConanFile):
    name = "Hello"
    version = "0.1"
"""


class ConanBuildTest(unittest.TestCase):

    def build_test(self):
        """ Try to reuse variables loaded from txt generator => deps_cpp_info
        """
        client = TestClient()
        client.save({CONANFILE: conanfile_dep})
        client.run("export lasote/testing")

        client.save({CONANFILE: conanfile_scope_env}, clean_first=True)
        client.run("install --build=missing")

        client.run("build")
        ref = PackageReference.loads("Hello/0.1@lasote/testing:"
                                     "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        package_folder = client.paths.package(ref).replace("\\", "/")
        self.assertIn("Project: INCLUDE PATH: %s/include" % package_folder, client.user_io.out)
        self.assertIn("Project: HELLO ROOT PATH: %s" % package_folder, client.user_io.out)
        self.assertIn("Project: HELLO INCLUDE PATHS: %s/include"
                      % package_folder, client.user_io.out)
