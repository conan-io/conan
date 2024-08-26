import textwrap
import unittest

import pytest

from conan.test.utils.tools import TestClient


class ConanfileErrorsTest(unittest.TestCase):

    def test_copy_error(self):
        client = TestClient()
        conanfile = textwrap.dedent('''
            from conan import ConanFile

            class HelloConan(ConanFile):
                name = "hello"
                version = "0.1"
                exports = "*"
                def package(self):
                    self.copy2("*.h", dst="include", src=["include","platform"])
            ''')
        files = {"conanfile.py": conanfile, "test.txt": "Hello world"}
        client.save(files)
        client.run("export . --user=lasote --channel=stable")
        client.run("install --requires=hello/0.1@lasote/stable --build='*'", assert_error=True)
        self.assertIn("hello/0.1@lasote/stable: Error in package() method, line 9", client.out)
        self.assertIn('self.copy2("*.h", dst="include", src=["include","platform"]', client.out)
        self.assertIn("'HelloConan' object has no attribute 'copy2'", client.out)

    def test_copy_error2(self):
        client = TestClient()
        conanfile = textwrap.dedent('''
            from conan import ConanFile

            class HelloConan(ConanFile):
                name = "hello"
                version = "0.1"
                exports = "*"
                def package(self):
                    self.copy("*.h", dst="include", src=["include","platform"])
            ''')
        files = {"conanfile.py": conanfile, "test.txt": "Hello world"}
        client.save(files)
        client.run("export . --user=lasote --channel=stable")
        client.run("install --requires=hello/0.1@lasote/stable --build='*'", assert_error=True)
        self.assertIn("hello/0.1@lasote/stable: Error in package() method, line 9", client.out)
        self.assertIn('self.copy("*.h", dst="include", src=["include","platform"]', client.out)
        # It results that the error is different in different Python2/3 and OSs
        # self.assertIn("'list' object has no attribute 'replace'", client.out)

    def test_package_info_error(self):
        client = TestClient()
        conanfile = textwrap.dedent('''
            from conan import ConanFile

            class HelloConan(ConanFile):
                name = "hello"
                version = "0.1"
                exports = "*"
                def package_info(self):
                    self.copy2()
            ''')
        files = {"conanfile.py": conanfile, "test.txt": "Hello world"}
        client.save(files)
        client.run("export . --user=lasote --channel=stable")
        client.run("install --requires=hello/0.1@lasote/stable --build='*'", assert_error=True)
        self.assertIn("hello/0.1@lasote/stable: Error in package_info() method, line 9", client.out)
        self.assertIn('self.copy2()', client.out)
        self.assertIn("'HelloConan' object has no attribute 'copy2'", client.out)

    def test_config_error(self):
        client = TestClient()
        conanfile = textwrap.dedent('''
            from conan import ConanFile

            class HelloConan(ConanFile):
                name = "hello"
                version = "0.1"
                exports = "*"
                def configure(self):
                    self.copy2()
            ''')
        files = {"conanfile.py": conanfile, "test.txt": "Hello world"}
        client.save(files)
        client.run("export . --user=lasote --channel=stable")
        client.run("install --requires=hello/0.1@lasote/stable --build='*'", assert_error=True)

        self.assertIn("ERROR: hello/0.1@lasote/stable: Error in configure() method, line 9",
                      client.out)
        self.assertIn("self.copy2()", client.out)
        self.assertIn("AttributeError: 'HelloConan' object has no attribute 'copy2'""", client.out)

    def test_source_error(self):
        client = TestClient()
        conanfile = textwrap.dedent('''
            from conan import ConanFile

            class HelloConan(ConanFile):
                name = "hello"
                version = "0.1"
                exports = "*"
                def source(self):
                    self.copy2()
            ''')
        files = {"conanfile.py": conanfile, "test.txt": "Hello world"}
        client.save(files)
        client.run("export . --user=lasote --channel=stable")
        client.run("install --requires=hello/0.1@lasote/stable --build='*'", assert_error=True)
        self.assertIn("hello/0.1@lasote/stable: Error in source() method, line 9", client.out)
        self.assertIn('self.copy2()', client.out)
        self.assertIn("'HelloConan' object has no attribute 'copy2'", client.out)

    def test_duplicate_requires(self):
        client = TestClient()
        conanfile = textwrap.dedent('''
            [requires]
            foo/0.1@user/testing
            foo/0.2@user/testing
            ''')
        files = {"conanfile.txt": conanfile}
        client.save(files)
        client.run("install . --build='*'", assert_error=True)
        self.assertIn("ERROR: Duplicated requirement", client.out)

    def test_duplicate_requires_py(self):
        client = TestClient()
        conanfile = textwrap.dedent('''
            from conan import ConanFile

            class HelloConan(ConanFile):
                name = "hello"
                version = "0.1"
                requires = "foo/0.1@user/testing", "foo/0.2@user/testing"
            ''')
        files = {"conanfile.py": conanfile}
        client.save(files)
        client.run("export .", assert_error=True)
        self.assertIn("Duplicated requirement", client.out)


class TestWrongMethods:
    # https://github.com/conan-io/conan/issues/12961
    @pytest.mark.parametrize("requires", ["requires", "tool_requires",
                                          "test_requires", "build_requires"])
    def test_wrong_method_requires(self, requires):
        """ this is expected to be a relatively frequent user error, and the trace was
        very ugly and debugging complicated
        """
        c = TestClient()
        conanfile = textwrap.dedent(f"""
            from conan import ConanFile
            class Pkg(ConanFile):
                def {requires}(self):
                    pass
            """)
        c.save({"conanfile.py": conanfile})
        c.run("install .", assert_error=True)
        expected = "requirements" if requires == "requires" else "build_requirements"
        assert f" Wrong '{requires}' definition, did you mean '{expected}()'?" in c.out


def test_notduplicate_requires_py():
    client = TestClient()
    conanfile = textwrap.dedent('''
        from conan import ConanFile

        class HelloConan(ConanFile):
            name = "hello"
            version = "0.1"
            requires = "foo/0.1@user/testing"
            build_requires = "foo/0.2@user/testing"
        ''')
    files = {"conanfile.py": conanfile}
    client.save(files)
    client.run("export .")
    assert "hello/0.1: Exported" in client.out


def test_requirements_change_options():
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class HelloConan(ConanFile):
            name = "hello"
            version = "0.1"

            def requirements(self):
                self.options["mydep"].myoption = 3
        """)
    c.save({"conanfile.py": conanfile})
    c.run("create .", assert_error=True)
    assert "ERROR: hello/0.1: Dependencies options were defined incorrectly." in c.out


@pytest.mark.parametrize("property_name", ["libdir", "bindir", "includedir"])
@pytest.mark.parametrize("property_content", [[], ["mydir1", "mydir2"]])
def test_shorthand_bad_interface(property_name, property_content):
    c = TestClient(light=True)
    conanfile = textwrap.dedent(f"""
        from conan import ConanFile

        class HelloConan(ConanFile):
            name = "hello"
            version = "0.1"

            def package_info(self):
                self.cpp_info.{property_name}s = {property_content}
                self.output.info(self.cpp_info.{property_name})
        """)
    c.save({"conanfile.py": conanfile})
    c.run("create .", assert_error=True)
    if property_content:
        assert f"The {property_name} property is undefined because {property_name}s has more than one element." in c.out
    else:
        assert f"The {property_name} property is undefined because {property_name}s is empty." in c.out

