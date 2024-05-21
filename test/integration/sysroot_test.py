import unittest

from conan.test.utils.tools import TestClient


class SysrootTest(unittest.TestCase):

    def test(self):
        client = TestClient()
        sysroot = """from conan import ConanFile
class Pkg(ConanFile):
    def package_info(self):
        self.cpp_info.sysroot = "HelloSysRoot"
"""
        client.save({"conanfile.py": sysroot})
        client.run("create . --name=sysroot --version=0.1 --user=user --channel=testing")

        conanfile = """from conan import ConanFile
class Pkg(ConanFile):
    requires = "sysroot/0.1@user/testing"
    def build(self):
        self.output.info("PKG SYSROOT: %s" % self.dependencies["sysroot"].cpp_info.sysroot)
    def package_info(self):
        self.cpp_info.sysroot = "HelloSysRoot"
"""
        test_conanfile = """from conan import ConanFile
class Pkg(ConanFile):
    def requirements(self):
        self.requires(self.tested_reference_str)
    def build(self):
        self.output.info("Test SYSROOT: %s"
                          % self.dependencies["sysroot"].cpp_info.sysroot)
    def test(self):
        pass
"""
        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": test_conanfile})
        client.run("create . --name=pkg --version=0.1 --user=user --channel=testing")
        self.assertIn("pkg/0.1@user/testing: PKG SYSROOT: HelloSysRoot", client.out)
        self.assertIn("pkg/0.1@user/testing (test package): Test SYSROOT: HelloSysRoot", client.out)

        client.run("install .")
