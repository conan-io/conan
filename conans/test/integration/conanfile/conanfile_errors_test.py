import textwrap
import unittest

from conans.test.utils.tools import TestClient


class ConanfileErrorsTest(unittest.TestCase):

    def test_copy_error(self):
        client = TestClient()
        conanfile = textwrap.dedent('''
            from conans import ConanFile

            class HelloConan(ConanFile):
                name = "Hello"
                version = "0.1"
                exports = "*"
                def package(self):
                    self.copy2("*.h", dst="include", src=["include","platform"])
            ''')
        files = {"conanfile.py": conanfile, "test.txt": "Hello world"}
        client.save(files)
        client.run("export . lasote/stable")
        client.run("install Hello/0.1@lasote/stable --build", assert_error=True)
        self.assertIn("Hello/0.1@lasote/stable: Error in package() method, line 9", client.out)
        self.assertIn('self.copy2("*.h", dst="include", src=["include","platform"]', client.out)
        self.assertIn("'HelloConan' object has no attribute 'copy2'", client.out)

    def test_copy_error2(self):
        client = TestClient()
        conanfile = textwrap.dedent('''
            from conans import ConanFile

            class HelloConan(ConanFile):
                name = "Hello"
                version = "0.1"
                exports = "*"
                def package(self):
                    self.copy("*.h", dst="include", src=["include","platform"])
            ''')
        files = {"conanfile.py": conanfile, "test.txt": "Hello world"}
        client.save(files)
        client.run("export . lasote/stable")
        client.run("install Hello/0.1@lasote/stable --build", assert_error=True)
        self.assertIn("Hello/0.1@lasote/stable: Error in package() method, line 9", client.out)
        self.assertIn('self.copy("*.h", dst="include", src=["include","platform"]', client.out)
        # It results that the error is different in different Python2/3 and OSs
        # self.assertIn("'list' object has no attribute 'replace'", client.out)

    def test_package_info_error(self):
        client = TestClient()
        conanfile = textwrap.dedent('''
            from conans import ConanFile

            class HelloConan(ConanFile):
                name = "Hello"
                version = "0.1"
                exports = "*"
                def package_info(self):
                    self.copy2()
            ''')
        files = {"conanfile.py": conanfile, "test.txt": "Hello world"}
        client.save(files)
        client.run("export . lasote/stable")
        client.run("install Hello/0.1@lasote/stable --build", assert_error=True)
        self.assertIn("Hello/0.1@lasote/stable: Error in package_info() method, line 9", client.out)
        self.assertIn('self.copy2()', client.out)
        self.assertIn("'HelloConan' object has no attribute 'copy2'", client.out)

    def test_config_error(self):
        client = TestClient()
        conanfile = textwrap.dedent('''
            from conans import ConanFile

            class HelloConan(ConanFile):
                name = "Hello"
                version = "0.1"
                exports = "*"
                def configure(self):
                    self.copy2()
            ''')
        files = {"conanfile.py": conanfile, "test.txt": "Hello world"}
        client.save(files)
        client.run("export . lasote/stable")
        client.run("install Hello/0.1@lasote/stable --build", assert_error=True)

        self.assertIn("ERROR: Hello/0.1@lasote/stable: Error in configure() method, line 9",
                      client.out)
        self.assertIn("self.copy2()", client.out)
        self.assertIn("AttributeError: 'HelloConan' object has no attribute 'copy2'""", client.out)

    def test_source_error(self):
        client = TestClient()
        conanfile = textwrap.dedent('''
            from conans import ConanFile

            class HelloConan(ConanFile):
                name = "Hello"
                version = "0.1"
                exports = "*"
                def source(self):
                    self.copy2()
            ''')
        files = {"conanfile.py": conanfile, "test.txt": "Hello world"}
        client.save(files)
        client.run("export . lasote/stable")
        client.run("install Hello/0.1@lasote/stable --build", assert_error=True)
        self.assertIn("Hello/0.1@lasote/stable: Error in source() method, line 9", client.out)
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
        client.run("install . --build", assert_error=True)
        self.assertIn("ERROR: Duplicated requirement", client.out)

    def test_duplicate_requires_py(self):
        client = TestClient()
        conanfile = textwrap.dedent('''
            from conans import ConanFile

            class HelloConan(ConanFile):
                name = "Hello"
                version = "0.1"
                requires = "foo/0.1@user/testing", "foo/0.2@user/testing"
            ''')
        files = {"conanfile.py": conanfile}
        client.save(files)
        client.run("install . --build", assert_error=True)
        self.assertIn("Error while initializing requirements. Duplicated requirement", client.out)
