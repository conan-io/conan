import os
import textwrap
import unittest

import pytest

from conans.model.recipe_ref import RecipeReference
from conans.paths import CONANFILE
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, GenConanfile
from conans.util.files import load


class TestPackageTest(unittest.TestCase):

    def test_basic(self):
        client = TestClient()
        client.save({CONANFILE: GenConanfile().with_name("hello").with_version("0.1"),
                     "test_package/conanfile.py": GenConanfile().with_test("pass")})
        client.run("create . --user=lasote --channel=stable")
        self.assertIn("hello/0.1@lasote/stable: Calling source() ", client.out)
        self.assertIn("hello/0.1@lasote/stable: Generated conaninfo.txt", client.out)

    def test_test_only(self):
        test_conanfile = GenConanfile().with_test("pass")
        client = TestClient()
        client.save({CONANFILE: GenConanfile().with_name("hello").with_version("0.1"),
                     "test_package/conanfile.py": test_conanfile})
        client.run("create . --user=lasote --channel=stable")
        client.run("test test_package hello/0.1@lasote/stable")

        self.assertNotIn("Exporting package recipe", client.out)
        self.assertNotIn("Forced build from source", client.out)
        self.assertNotIn("Package '%s' created" % NO_SETTINGS_PACKAGE_ID, client.out)
        self.assertNotIn("Forced build from source", client.out)
        self.assertIn("hello/0.1@lasote/stable: Already installed!", client.out)

        client.save({"test_package/conanfile.py": test_conanfile}, clean_first=True)
        client.run("test test_package hello/0.1@lasote/stable")
        self.assertNotIn("hello/0.1@lasote/stable: Configuring sources", client.out)
        self.assertNotIn("hello/0.1@lasote/stable: Generated conaninfo.txt", client.out)
        self.assertIn("hello/0.1@lasote/stable: Already installed!", client.out)
        self.assertIn("hello/0.1@lasote/stable (test package): Running test()", client.out)

    def test_wrong_version(self):
        test_conanfile = GenConanfile().with_test("pass").with_require("hello/0.2@user/cc")
        client = TestClient()
        client.save({CONANFILE: GenConanfile().with_name("hello").with_version("0.1"),
                     "test_package/conanfile.py": test_conanfile})
        client.run("create . --user=user --channel=channel", assert_error=True)
        assert "Duplicated requirement: hello/0.1@user/channel" in client.out

    def test_other_requirements(self):
        test_conanfile = (GenConanfile().with_require("other/0.2@user2/channel2")
                                        .with_test("pass"))
        client = TestClient()
        other_conanfile = GenConanfile().with_name("other").with_version("0.2")
        client.save({CONANFILE: other_conanfile})
        client.run("export . --user=user2 --channel=channel2")
        client.run("install --requires=other/0.2@user2/channel2 --build='*'")
        client.save({CONANFILE: GenConanfile().with_name("hello").with_version("0.1"),
                     "test_package/conanfile.py": test_conanfile})
        client.run("create . --user=user --channel=channel")
        self.assertIn("hello/0.1@user/channel: Calling source()", client.out)
        self.assertIn("hello/0.1@user/channel: Generated conaninfo.txt", client.out)

        # explicit override of user/channel works
        client.run("create . --user=lasote --channel=stable")
        self.assertIn("hello/0.1@lasote/stable: Calling source()", client.out)
        self.assertIn("hello/0.1@lasote/stable: Generated conaninfo.txt", client.out)

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

    def test_check_version(self):
        client = TestClient()
        client.save({CONANFILE: GenConanfile()})
        client.run("create . --name=dep --version=1.1")
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                requires = "dep/1.1"
                def build(self):
                    ref = self.dependencies["dep"].ref
                    self.output.info("BUILD Dep VERSION %s" % ref.version)
            """)
        test_conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                def requirements(self):
                    self.requires(self.tested_reference_str)
                def build(self):
                    ref = self.dependencies["hello"].ref
                    self.output.info("BUILD HELLO VERSION %s" % ref.version)
                def test(self):
                    ref = self.dependencies["hello"].ref
                    self.output.info("TEST HELLO VERSION %s" % ref.version)
            """)
        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": test_conanfile})
        client.run("create . --name=hello --version=0.1")
        self.assertIn("hello/0.1: BUILD Dep VERSION 1.1", client.out)
        self.assertIn("hello/0.1 (test package): BUILD HELLO VERSION 0.1", client.out)
        self.assertIn("hello/0.1 (test package): TEST HELLO VERSION 0.1", client.out)


class ConanTestTest(unittest.TestCase):

    def test_partial_reference(self):
        # Create two packages to test with the same test
        conanfile = '''
from conan import ConanFile

class HelloConan(ConanFile):
    name = "hello"
    version = "0.1"
'''
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("create . --user=conan --channel=stable")
        client.run("create . --user=conan --channel=testing")
        client.run("create . --user=conan --channel=foo")

        def test(conanfile_test, test_reference, path=None):
            path = path or "."
            client.save({os.path.join(path, CONANFILE): conanfile_test}, clean_first=True)
            client.run("test %s %s" % (path, test_reference))

        # Specify a valid name
        test('''
from conan import ConanFile

class HelloTestConan(ConanFile):
    def requirements(self):
        self.requires(self.tested_reference_str)
    def test(self):
        self.output.warning("Tested ok!")
''', "hello/0.1@conan/stable")
        self.assertIn("Tested ok!", client.out)

    def test_test_package_env(self):
        client = TestClient()
        conanfile = '''
from conan import ConanFile

class HelloConan(ConanFile):
    name = "hello"
    version = "0.1"
    def package_info(self):
        self.buildenv_info.define("MYVAR", "new/pythonpath/value")

        '''
        test_package = '''
import os, platform
from conan import ConanFile
from conan.tools.env import VirtualBuildEnv

class HelloTestConan(ConanFile):
    generators = "VirtualBuildEnv"

    def requirements(self):
        self.build_requires(self.tested_reference_str)

    def build(self):
        build_env = VirtualBuildEnv(self).vars()
        with build_env.apply():
            assert("new/pythonpath/value" in os.environ["MYVAR"])

    def test(self):
        build_env = VirtualBuildEnv(self).vars()
        with build_env.apply():
            assert("new/pythonpath/value" in os.environ["MYVAR"])
'''

        client.save({"conanfile.py": conanfile, "test_package/conanfile.py": test_package})
        client.run("create . --user=lasote --channel=testing")
        client.run("test test_package hello/0.1@lasote/testing")

    def test_fail_test_package(self):
        client = TestClient()
        conanfile = """
from conan import ConanFile
from conan.tools.files import copy

class HelloConan(ConanFile):
    name = "hello"
    version = "0.1"
    exports_sources = "*"

    def package(self):
        copy(self, "*", self.source_folder, self.package_folder)
"""
        test_conanfile = """
from conan import ConanFile

class HelloReuseConan(ConanFile):
    def requirements(self):
        self.requires(self.tested_reference_str)
    def test(self):
        pass
"""
        client.save({"conanfile.py": conanfile,
                     "FindXXX.cmake": "Hello FindCmake",
                     "test/conanfile.py": test_conanfile})
        client.run("create . --user=lasote --channel=stable")
        ref = RecipeReference.loads("hello/0.1@lasote/stable")
        client.run(f"test test {str(ref)}")
        pref = client.get_latest_package_reference(ref, NO_SETTINGS_PACKAGE_ID)
        self.assertEqual("Hello FindCmake",
                         load(os.path.join(client.get_latest_pkg_layout(pref).package(), "FindXXX.cmake")))
        client.save({"FindXXX.cmake": "Bye FindCmake"})
        client.run(f"test test {str(ref)}")  # Test do not rebuild the package
        pref = client.get_latest_package_reference(ref, NO_SETTINGS_PACKAGE_ID)
        self.assertEqual("Hello FindCmake",
                         load(os.path.join(client.get_latest_pkg_layout(pref).package(), "FindXXX.cmake")))
        client.run("create . --user=lasote --channel=stable")  # create rebuild the package
        pref = client.get_latest_package_reference(ref, NO_SETTINGS_PACKAGE_ID)
        self.assertEqual("Bye FindCmake",
                         load(os.path.join(client.get_latest_pkg_layout(pref).package(), "FindXXX.cmake")))


def test_no_reference_in_test_package():
    client = TestClient()
    test_conanfile = textwrap.dedent("""
        from conan import ConanFile
        import os

        class HelloReuseConan(ConanFile):
            def test(self):
                self.output.warning("At test: {}".format(self.tested_reference_str))
        """)

    client.save({"conanfile.py": GenConanfile(), "test_package/conanfile.py": test_conanfile})
    client.run("create . --name=foo --version=1.0", assert_error=True)
    assert "doesn't declare any requirement, use `self.tested_reference_str` to require the " \
           "package being created" in client.out


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
    from conan import ConanFile
    import os

    class HelloReuseConan(ConanFile):

        def generate(self):
            self.output.warning("At generate: {}".format(self.tested_reference_str))
            assert len(self.dependencies.values()) == 1
            assert len(self.dependencies.build.values()) == 1

        def build(self):
            self.output.warning("At build: {}".format(self.tested_reference_str))

        def build_requirements(self):
            self.output.warning("At build_requirements: {}".format(self.tested_reference_str))
            self.build_requires(self.tested_reference_str)

        def test(self):
            self.output.warning("At test: {}".format(self.tested_reference_str))
    """)

    client.save({"conanfile.py": GenConanfile(), "test_package/conanfile.py": test_conanfile})
    client.run("create . --name=foo --version=1.0")
    for method in ("generate", "build", "build_requirements", "test"):
        assert "At {}: foo/1.0".format(method) in client.out


def test_folder_output():
    """ the "conan test" command should also follow the test_output layout folder
    """
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("hello", "0.1")})
    c.run("create .")
    c.save({"test_package/conanfile.py": GenConanfile().with_test("pass").with_settings("build_type")
                                                       .with_generator("CMakeDeps")})
    # c.run("create .")
    c.run("test test_package hello/0.1@")
    assert os.path.exists(os.path.join(c.current_folder,
                                       "test_package/test_output/build/generators/hello-config.cmake"))
