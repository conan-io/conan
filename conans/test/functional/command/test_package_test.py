import os
import textwrap
import unittest

from conans.client import tools
from conans.paths import CONANFILE
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, GenConanfile


class TestPackageTest(unittest.TestCase):

    def basic_test(self):
        client = TestClient()
        client.save({CONANFILE: GenConanfile().with_name("Hello").with_version("0.1"),
                     "test_package/conanfile.py": GenConanfile().with_test("pass")})
        client.run("create . lasote/stable")
        self.assertIn("Hello/0.1@lasote/stable: Configuring sources", client.out)
        self.assertIn("Hello/0.1@lasote/stable: Generated conaninfo.txt", client.out)

    def test_only_test(self):
        test_conanfile = GenConanfile().with_test("pass")
        client = TestClient()
        client.save({CONANFILE: GenConanfile().with_name("Hello").with_version("0.1"),
                     "test_package/conanfile.py": test_conanfile})
        client.run("create . lasote/stable")
        client.run("test test_package Hello/0.1@lasote/stable")

        self.assertNotIn("Exporting package recipe", client.out)
        self.assertNotIn("Forced build from source", client.out)
        self.assertNotIn("Package '%s' created" % NO_SETTINGS_PACKAGE_ID, client.out)
        self.assertNotIn("Forced build from source", client.out)
        self.assertIn("Hello/0.1@lasote/stable: Already installed!", client.out)

        client.save({"test_package/conanfile.py": test_conanfile}, clean_first=True)
        client.run("test test_package Hello/0.1@lasote/stable")
        self.assertNotIn("Hello/0.1@lasote/stable: Configuring sources", client.out)
        self.assertNotIn("Hello/0.1@lasote/stable: Generated conaninfo.txt", client.out)
        self.assertIn("Hello/0.1@lasote/stable: Already installed!", client.out)
        self.assertIn("Hello/0.1@lasote/stable (test package): Running test()", client.out)

    def wrong_version_test(self):
        # FIXME Conan 2.0: an incompatible requirement in test_package do nothing
        test_conanfile = GenConanfile().with_test("pass").with_require("Hello/0.2@user/cc")
        client = TestClient()
        client.save({CONANFILE: GenConanfile().with_name("Hello").with_version("0.1"),
                     "test_package/conanfile.py": test_conanfile})
        client.run("create . user/channel")
        self.assertNotIn("Hello/0.2", client.out)

    def other_requirements_test(self):
        test_conanfile = (GenConanfile().with_require("other/0.2@user2/channel2")
                                        .with_require("Hello/0.1@user/channel")
                                        .with_test("pass"))
        client = TestClient()
        other_conanfile = GenConanfile().with_name("other").with_version("0.2")
        client.save({CONANFILE: other_conanfile})
        client.run("export . user2/channel2")
        client.run("install other/0.2@user2/channel2 --build")
        client.save({CONANFILE: GenConanfile().with_name("Hello").with_version("0.1"),
                     "test_package/conanfile.py": test_conanfile})
        client.run("create . user/channel")
        self.assertIn("Hello/0.1@user/channel: Configuring sources", client.out)
        self.assertIn("Hello/0.1@user/channel: Generated conaninfo.txt", client.out)

        # explicit override of user/channel works
        client.run("create . lasote/stable")
        self.assertIn("Hello/0.1@lasote/stable: Configuring sources", client.out)
        self.assertIn("Hello/0.1@lasote/stable: Generated conaninfo.txt", client.out)

    def test_with_path_errors_test(self):
        client = TestClient()
        client.save({"conanfile.txt": "contents"}, clean_first=True)

        # Path with conanfile.txt
        client.run("test conanfile.txt other/0.2@user2/channel2", assert_error=True)

        self.assertIn("A conanfile.py is needed, %s is not acceptable"
                      % os.path.join(client.current_folder, "conanfile.txt"),
                      client.out)

        # Path with wrong conanfile path
        client.run("test not_real_dir/conanfile.py other/0.2@user2/channel2", assert_error=True)
        self.assertIn("Conanfile not found at %s"
                      % os.path.join(client.current_folder, "not_real_dir", "conanfile.py"),
                      client.out)

    def build_folder_handling_test(self):
        test_conanfile = GenConanfile().with_test("pass")
        # Create a package which can be tested afterwards.
        client = TestClient()
        client.save({CONANFILE: GenConanfile().with_name("Hello").with_version("0.1")},
                    clean_first=True)
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
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "test_package",
                                                    "build_folder")))
        self.assertFalse(os.path.exists(default_build_dir))

    def check_version_test(self):
        client = TestClient()
        dep = textwrap.dedent("""
            from conans import ConanFile
            class Dep(ConanFile):
                def package_info(self):
                    self.cpp_info.name = "MyDep"
            """)
        client.save({CONANFILE: dep})
        client.run("create . dep/1.1@")
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                requires = "dep/1.1"
                def build(self):
                    info = self.deps_cpp_info["dep"]
                    self.output.info("BUILD Dep %s VERSION %s" %
                        (info.get_name("txt"), info.version))
                def package_info(self):
                    self.cpp_info.names["txt"] = "MyHello"
            """)
        test_conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                def build(self):
                    info = self.deps_cpp_info["hello"]
                    self.output.info("BUILD HELLO %s VERSION %s" %
                        (info.get_name("txt"), info.version))
                def test(self):
                    info = self.deps_cpp_info["hello"]
                    self.output.info("TEST HELLO %s VERSION %s" %
                        (info.get_name("txt"), info.version))
            """)
        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": test_conanfile})
        client.run("create . hello/0.1@")
        self.assertIn("hello/0.1: BUILD Dep MyDep VERSION 1.1", client.out)
        self.assertIn("hello/0.1 (test package): BUILD HELLO MyHello VERSION 0.1", client.out)
        self.assertIn("hello/0.1 (test package): TEST HELLO MyHello VERSION 0.1", client.out)
