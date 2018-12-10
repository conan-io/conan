import unittest

from conans.test.utils.tools import TestClient


class OptimizeConanFileLoadTest(unittest.TestCase):

    def test_multiple_load(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
mycounter = 0
class Pkg(ConanFile):
    def configure(self):
        global mycounter
        mycounter += 1
        self.output.info("My Counter %s" % mycounter)
"""
        client.save({"conanfile.py": conanfile})

        client.run("create . Build/0.1@user/testing")

        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": conanfile + "    def test(self): pass",
                     "myprofile": "[build_requires]\nBuild/0.1@user/testing"})

        client.run("create . Pkg/0.1@user/testing -pr=myprofile")
        self.assertIn("Build/0.1@user/testing: My Counter 2", client.out)
