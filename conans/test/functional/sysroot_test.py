import os
import unittest

from conans.test.utils.tools import TestClient


class SysrootTest(unittest.TestCase):

    def test(self):
        client = TestClient()
        sysroot = """from conans import ConanFile
class Pkg(ConanFile):
    def package_info(self):
        self.cpp_info.sysroot = "HelloSysRoot"
"""
        client.save({"conanfile.py": sysroot})
        client.run("create . sysroot/0.1@user/testing")

        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    build_requires = "sysroot/0.1@user/testing"
    def build(self):
        self.output.info("PKG SYSROOT: %s" % self.deps_cpp_info.sysroot)
    def package_info(self):
        self.cpp_info.sysroot = "HelloSysRoot"
"""
        test_conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    def build(self):
        self.output.info("Test SYSROOT: %s" % self.deps_cpp_info.sysroot)
    def test(self):
        pass
"""
        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": test_conanfile})
        client.run("create . Pkg/0.1@user/testing")
        self.assertIn("Pkg/0.1@user/testing: PKG SYSROOT: HelloSysRoot", client.out)
        self.assertIn("Pkg/0.1@user/testing (test package): Test SYSROOT: HelloSysRoot", client.out)

        # Install conanfile and check conaninfo.txt
        client.run("install .")
        bili = client.load("conanbuildinfo.txt")
        self.assertIn(os.linesep.join(["[sysroot_sysroot]", "HelloSysRoot"]), bili)
        self.assertIn(os.linesep.join(["[sysroot]", "HelloSysRoot"]), bili)
