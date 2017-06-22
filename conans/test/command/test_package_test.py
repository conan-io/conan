import unittest
from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient

conanfile = '''
from conans import ConanFile

class ConanLib(ConanFile):
    name = "Hello"
    version = "0.1"
'''


class TestPackageTest(unittest.TestCase):

    def basic_test(self):
        test_conanfile = '''
from conans import ConanFile

class TestConanLib(ConanFile):
    def test(self):
        pass
'''
        client = TestClient()
        client.save({CONANFILE: conanfile,
                     "test_package/conanfile.py": test_conanfile})
        client.run("test_package -a lasote -c stable")
        self.assertIn("Hello/0.1@lasote/stable: Configuring sources", client.user_io.out)
        self.assertIn("Hello/0.1@lasote/stable: Generated conaninfo.txt", client.user_io.out)

    def wrong_version_test(self):
        test_conanfile = '''
from conans import ConanFile

class TestConanLib(ConanFile):
    requires = "Hello/0.2@user/channel"
    def test(self):
        pass
'''
        client = TestClient()
        client.save({CONANFILE: conanfile,
                     "test_package/conanfile.py": test_conanfile})
        client.run("test_package")
        self.assertIn("Hello/0.1@user/channel: Configuring sources", client.user_io.out)
        self.assertIn("Hello/0.1@user/channel: Generated conaninfo.txt", client.user_io.out)

    def other_requirements_test(self):
        test_conanfile = '''
from conans import ConanFile

class TestConanLib(ConanFile):
    requires = "other/0.2@user2/channel2", "Hello/0.2@user/channel"
    def test(self):
        pass
'''
        client = TestClient()
        other_conanfile = """
from conans import ConanFile
class ConanLib(ConanFile):
    name = "other"
    version = "0.2"
"""
        client.save({CONANFILE: other_conanfile})
        client.run("export user2/channel2")
        client.run("install other/0.2@user2/channel2 --build")
        client.save({CONANFILE: conanfile,
                     "test_package/conanfile.py": test_conanfile})
        client.run("test_package")
        self.assertIn("Hello/0.1@user/channel: Configuring sources", client.user_io.out)
        self.assertIn("Hello/0.1@user/channel: Generated conaninfo.txt", client.user_io.out)
