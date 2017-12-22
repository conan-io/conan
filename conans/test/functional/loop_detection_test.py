import unittest
from conans.test.utils.tools import TestClient


class LoopDectectionTest(unittest.TestCase):

    def copy_error_test(self):
        client = TestClient()
        conanfile = '''
from conans import ConanFile

class Package{number}Conan(ConanFile):
    name = "Package{number}"
    version = "0.1"
    requires = "Package{dep}/0.1@lasote/stable"
'''
        for package_number in [1, 2, 3]:
            content = conanfile.format(number=package_number, dep=package_number % 3 + 1)
            files = {"conanfile.py": content}

            client.save(files, clean_first=True)
            client.run("export . lasote/stable")

        client.run("install Package3/0.1@lasote/stable --build", ignore_error=True)
        self.assertIn("ERROR: Loop detected: Package3/0.1@lasote/stable->"
                      "Package1/0.1@lasote/stable->Package2/0.1@lasote/stable",
                      client.user_io.out)
