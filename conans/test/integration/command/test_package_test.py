import os
import textwrap
import unittest

from conans.client import tools
from conans.model.ref import PackageReference
from conans.paths import CONANFILE
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, GenConanfile
from conans.util.files import load


class TestPackageTest(unittest.TestCase):

    def test_basic(self):
        client = TestClient()
        client.save({CONANFILE: GenConanfile().with_name("Hello").with_version("0.1"),
                     "test_package/conanfile.py": GenConanfile().with_test("pass")})
        client.run("create . lasote/stable")
        self.assertIn("Hello/0.1@lasote/stable: Configuring sources", client.out)
        self.assertIn("Hello/0.1@lasote/stable: Generated conaninfo.txt", client.out)

    def test_test_only(self):
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

    def test_wrong_version(self):
        # FIXME Conan 2.0: an incompatible requirement in test_package do nothing
        test_conanfile = GenConanfile().with_test("pass").with_require("Hello/0.2@user/cc")
        client = TestClient()
        client.save({CONANFILE: GenConanfile().with_name("Hello").with_version("0.1"),
                     "test_package/conanfile.py": test_conanfile})
        client.run("create . user/channel")
        self.assertNotIn("Hello/0.2", client.out)

    def test_other_requirements(self):
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

    def test_test_with_path_errors(self):
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

    def test_build_folder_handling(self):
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

    def test_check_version(self):
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


class ConanTestTest(unittest.TestCase):

    def test_partial_reference(self):
        # Create two packages to test with the same test
        conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
'''
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("create . conan/stable")
        client.run("create . conan/testing")
        client.run("create . conan/foo")

        def test(conanfile_test, test_reference, path=None):
            path = path or "."
            client.save({os.path.join(path, CONANFILE): conanfile_test}, clean_first=True)
            client.run("test %s %s" % (path, test_reference))

        # Specify a valid name
        test('''
from conans import ConanFile

class HelloTestConan(ConanFile):
    requires = ["Hello/0.1@conan/stable", ]
    def test(self):
        self.output.warn("Tested ok!")
''', "Hello/0.1@conan/stable")
        self.assertIn("Tested ok!", client.out)

        # Specify a complete reference but not matching with the requires, it's ok, the
        # require could be a tool or whatever
        test('''
from conans import ConanFile

class HelloTestConan(ConanFile):
    requires = "Hello/0.1@conan/stable"
    def test(self):
        self.output.warn("Tested ok!")
''', "Hello/0.1@conan/foo")
        self.assertIn("Tested ok!", client.out)

    def test_test_package_env(self):
        client = TestClient()
        conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    def package_info(self):
        self.env_info.PYTHONPATH.append("new/pythonpath/value")
        '''
        test_package = '''
import os
from conans import ConanFile

class HelloTestConan(ConanFile):
    requires = "Hello/0.1@lasote/testing"

    def build(self):
        assert("new/pythonpath/value" in os.environ["PYTHONPATH"])

    def test(self):
        assert("new/pythonpath/value" in os.environ["PYTHONPATH"])
'''

        client.save({"conanfile.py": conanfile, "test_package/conanfile.py": test_package})
        client.run("export . lasote/testing")
        client.run("test test_package Hello/0.1@lasote/testing --build missing")

    def test_fail_test_package(self):
        client = TestClient()
        conanfile = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    exports = "*"

    def package(self):
        self.copy("*")
"""
        test_conanfile = """
from conans import ConanFile, CMake
import os

class HelloReuseConan(ConanFile):
    requires = "Hello/0.1@lasote/stable"

    def test(self):
        pass
"""
        client.save({"conanfile.py": conanfile,
                     "FindXXX.cmake": "Hello FindCmake",
                     "test/conanfile.py": test_conanfile})
        client.run("create . lasote/stable")
        client.run("test test Hello/0.1@lasote/stable")
        pref = PackageReference.loads("Hello/0.1@lasote/stable:%s" % NO_SETTINGS_PACKAGE_ID)
        self.assertEqual("Hello FindCmake",
                         load(os.path.join(client.cache.package_layout(pref.ref).package(pref), "FindXXX.cmake")))
        client.save({"FindXXX.cmake": "Bye FindCmake"})
        client.run("test test Hello/0.1@lasote/stable")  # Test do not rebuild the package
        self.assertEqual("Hello FindCmake",
                         load(os.path.join(client.cache.package_layout(pref.ref).package(pref), "FindXXX.cmake")))
        client.run("create . lasote/stable")  # create rebuild the package
        self.assertEqual("Bye FindCmake",
                         load(os.path.join(client.cache.package_layout(pref.ref).package(pref), "FindXXX.cmake")))


def test_tested_reference_str():
    """
    At the test_package/conanfile the variable `self.tested_reference_str` is injected with the
    str of the reference being tested. It is available in all the methods.

    Compatibility with Conan 2.0:
    If the 'test_type' is set to "explicit" the require won't be automatically injected and has to
    be the user the one injecting the require or the build require using the
    `self.tested_reference_str`. This 'test_type' can be removed in 2.0 if we consider it has
    to be always explicit. The recipes will still work in Conan 2.0 because the 'test_type' will be
    ignored.
    """
    client = TestClient()
    test_conanfile = textwrap.dedent("""
    from conans import ConanFile, CMake
    import os

    class HelloReuseConan(ConanFile):

        test_type = "explicit"

        def generate(self):
            self.output.warn("At generate: {}".format(self.tested_reference_str))
            assert len(self.dependencies.values()) == 1
            assert len(self.dependencies.build.values()) == 1

        def build(self):
            self.output.warn("At build: {}".format(self.tested_reference_str))

        def build_requirements(self):
            self.output.warn("At build_requirements: {}".format(self.tested_reference_str))
            self.build_requires(self.tested_reference_str)

        def test(self):
            self.output.warn("At test: {}".format(self.tested_reference_str))
    """)

    client.save({"conanfile.py": GenConanfile(), "test_package/conanfile.py": test_conanfile})
    client.run("create . foo/1.0@")
    for method in ("generate", "build", "build_requirements", "test"):
        assert "At {}: foo/1.0".format(method) in client.out

