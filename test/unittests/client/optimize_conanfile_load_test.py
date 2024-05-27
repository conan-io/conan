import unittest

from conan.test.utils.tools import TestClient


class OptimizeConanFileLoadTest(unittest.TestCase):

    def test_multiple_load(self):
        """ when a conanfile is used more than once in a dependency graph, the python file
        should be read and interpreted just once, then instance 2 different ConanFile
        objects. The module global value "mycounter" is global to all instances, this
        should be discouraged to use as if it was an instance value.
        In this test there are 2 nodes "build/0.1" as it is a build-requires of both the
        conanfile.py and the test_package/conanfile.py
        """
        client = TestClient()
        conanfile = """from conan import ConanFile
mycounter = 0
class Pkg(ConanFile):
    mycounter2 = 0
    def configure(self):
        global mycounter
        mycounter += 1
        self.mycounter2 += 1
        self.output.info("MyCounter1 %s, MyCounter2 %s" % (mycounter, self.mycounter2))
"""
        client.save({"conanfile.py": conanfile})

        client.run("create . --name=build --version=0.1 --user=user --channel=testing")

        test_conanfile = conanfile + """
    def requirements(self):
        self.requires(self.tested_reference_str)

    def test(self):
        pass
        """
        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": test_conanfile,
                     "myprofile": "[tool_requires]\nbuild/0.1@user/testing"})

        client.run("create . --name=pkg --version=0.1 --user=user --channel=testing -pr=myprofile")
        self.assertIn("build/0.1@user/testing: MyCounter1 2, MyCounter2 1", client.out)
