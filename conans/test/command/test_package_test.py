import unittest
import os
from conans import tools
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
        client.run("create . lasote/stable")
        self.assertIn("Hello/0.1@lasote/stable: Configuring sources", client.user_io.out)
        self.assertIn("Hello/0.1@lasote/stable: Generated conaninfo.txt", client.user_io.out)

    def test_only_test(self):
        test_conanfile = '''
from conans import ConanFile

class TestConanLib(ConanFile):
    def test(self):
        pass
'''
        client = TestClient()
        client.save({CONANFILE: conanfile,
                     "test_package/conanfile.py": test_conanfile})
        client.run("create . lasote/stable")
        client.run("test test_package Hello/0.1@lasote/stable")

        self.assertNotIn("Exporting package recipe", client.out)
        self.assertNotIn("WARN: Forced build from source", client.out)
        self.assertNotIn("Package '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9' created", client.out)
        self.assertNotIn("WARN: Forced build from source", client.out)
        self.assertIn("Hello/0.1@lasote/stable: Already installed!", client.out)

        client.save({"test_package/conanfile.py": test_conanfile}, clean_first=True)
        client.run("test test_package Hello/0.1@lasote/stable")
        self.assertNotIn("Hello/0.1@lasote/stable: Configuring sources", client.out)
        self.assertNotIn("Hello/0.1@lasote/stable: Generated conaninfo.txt", client.out)
        self.assertIn("Hello/0.1@lasote/stable: Already installed!", client.out)
        self.assertIn("Hello/0.1@lasote/stable (test package): Running test()", client.out)

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
        client.run("create . user/channel")
        self.assertNotIn("Hello/0.2", client.out)

    def other_requirements_test(self):
        test_conanfile = '''
from conans import ConanFile

class TestConanLib(ConanFile):
    requires = "other/0.2@user2/channel2", "Hello/0.1@user/channel"
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
        client.run("export . user2/channel2")
        client.run("install other/0.2@user2/channel2 --build")
        client.save({CONANFILE: conanfile,
                     "test_package/conanfile.py": test_conanfile})
        client.run("create . user/channel")
        self.assertIn("Hello/0.1@user/channel: Configuring sources", client.user_io.out)
        self.assertIn("Hello/0.1@user/channel: Generated conaninfo.txt", client.user_io.out)

        # explicit override of user/channel works
        client.run("create . lasote/stable")
        self.assertIn("Hello/0.1@lasote/stable: Configuring sources", client.user_io.out)
        self.assertIn("Hello/0.1@lasote/stable: Generated conaninfo.txt", client.user_io.out)

    def test_with_path_errors_test(self):
        client = TestClient()
        client.save({"conanfile.txt": "contents"}, clean_first=True)

        # Path with conanfile.txt
        error = client.run("test conanfile.txt other/0.2@user2/channel2", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("A conanfile.py is needed (not valid conanfile.txt)", client.out)

        # Path with wrong conanfile path
        error = client.run("test not_real_dir/conanfile.py other/0.2@user2/channel2",
                           ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Conanfile not found: %s" % os.path.join(client.current_folder, "not_real_dir",
                                                               "conanfile.py"), client.out)

    def build_folder_handling_test(self):
        test_conanfile = '''
from conans import ConanFile

class TestConanLib(ConanFile):
    def test(self):
        pass
'''
        # Create a package which can be tested afterwards.
        client = TestClient()
        client.save({CONANFILE: conanfile}, clean_first=True)
        client.run("create . lasote/stable")

        # Test the default behavior.
        default_build_dir = os.path.join(client.current_folder, "test_package", "build")
        client.save({"test_package/conanfile.py": test_conanfile}, clean_first=True)
        client.run("test test_package Hello/0.1@lasote/stable")
        self.assertTrue(os.path.exists(default_build_dir))

        # Test if the specified build folder is respected.
        client.save({"test_package/conanfile.py": test_conanfile}, clean_first=True)
        client.run("test -tbf=build_folder test_package Hello/0.1@lasote/stable")
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "build_folder")))
        self.assertFalse(os.path.exists(default_build_dir))

        # Test if using a temporary test folder can be enabled via the environment variable.
        client.save({"test_package/conanfile.py": test_conanfile}, clean_first=True)
        with tools.environment_append({"CONAN_TEMP_TEST_FOLDER": "True"}):
            client.run("test test_package Hello/0.1@lasote/stable")
        self.assertFalse(os.path.exists(default_build_dir))

        # Test if using a temporary test folder can be enabled via the config file.
        client.run('config set general.temp_test_folder=True')
        client.run("test test_package Hello/0.1@lasote/stable")
        self.assertFalse(os.path.exists(default_build_dir))

        # Test if the specified build folder is respected also when the use of
        # temporary test folders is enabled in the config file.
        client.run("test -tbf=test_package/build_folder test_package Hello/0.1@lasote/stable")
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "test_package", "build_folder")))
        self.assertFalse(os.path.exists(default_build_dir))
