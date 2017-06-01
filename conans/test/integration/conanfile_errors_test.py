import unittest
from conans.test.utils.tools import TestClient


class ConanfileErrorsTest(unittest.TestCase):

    def copy_error_test(self):
        client = TestClient()
        conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    exports = "*"
    def package(self):
        self.copy2("*.h", dst="include", src=["include","platform"])
'''
        files = {"conanfile.py": conanfile, "test.txt": "Hello world"}
        client.save(files)
        client.run("export lasote/stable")
        client.run("install Hello/0.1@lasote/stable --build", ignore_error=True)
        self.assertIn("Hello/0.1@lasote/stable: Error in package() method, line 9",
                      client.user_io.out)
        self.assertIn('self.copy2("*.h", dst="include", src=["include","platform"]',
                      client.user_io.out)
        self.assertIn("'HelloConan' object has no attribute 'copy2'",
                      client.user_io.out)

    def copy_error2_test(self):
        client = TestClient()
        conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    exports = "*"
    def package(self):
        self.copy("*.h", dst="include", src=["include","platform"])
'''
        files = {"conanfile.py": conanfile, "test.txt": "Hello world"}
        client.save(files)
        client.run("export lasote/stable")
        client.run("install Hello/0.1@lasote/stable --build", ignore_error=True)
        self.assertIn("Hello/0.1@lasote/stable: Error in package() method, line 9",
                      client.user_io.out)
        self.assertIn('self.copy("*.h", dst="include", src=["include","platform"]',
                      client.user_io.out)
        # It results that the error is different in different Python2/3 and OSs
        # self.assertIn("'list' object has no attribute 'replace'", client.user_io.out)

    def package_info_error_test(self):
        client = TestClient()
        conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    exports = "*"
    def package_info(self):
        self.copy2()
'''
        files = {"conanfile.py": conanfile, "test.txt": "Hello world"}
        client.save(files)
        client.run("export lasote/stable")
        client.run("install Hello/0.1@lasote/stable --build", ignore_error=True)
        self.assertIn("Hello/0.1@lasote/stable: Error in package_info() method, line 9",
                      client.user_io.out)
        self.assertIn('self.copy2()',
                      client.user_io.out)
        self.assertIn("'HelloConan' object has no attribute 'copy2'",
                      client.user_io.out)

    def config_error_test(self):
        client = TestClient()
        conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    exports = "*"
    def configure(self):
        self.copy2()
'''
        files = {"conanfile.py": conanfile, "test.txt": "Hello world"}
        client.save(files)
        client.run("export lasote/stable")
        client.run("install Hello/0.1@lasote/stable --build", ignore_error=True)

        self.assertIn("""ERROR: Hello/0.1@lasote/stable: Error in configure() method, line 9
	self.copy2()
	AttributeError: 'HelloConan' object has no attribute 'copy2'""", client.user_io.out)

    def source_error_test(self):
        client = TestClient()
        conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    exports = "*"
    def source(self):
        self.copy2()
'''
        files = {"conanfile.py": conanfile, "test.txt": "Hello world"}
        client.save(files)
        client.run("export lasote/stable")
        client.run("install Hello/0.1@lasote/stable --build", ignore_error=True)
        self.assertIn("Hello/0.1@lasote/stable: Error in source() method, line 9",
                      client.user_io.out)
        self.assertIn('self.copy2()',
                      client.user_io.out)
        self.assertIn("'HelloConan' object has no attribute 'copy2'",
                      client.user_io.out)

    def duplicate_requires_test(self):
        client = TestClient()
        conanfile = '''
[requires]
foo/0.1@user/testing
foo/0.2@user/testing
'''
        files = {"conanfile.txt": conanfile}
        client.save(files)
        error = client.run("install . --build", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Duplicated requirement", client.user_io.out)

    def duplicate_requires_py_test(self):
        client = TestClient()
        conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    requires = "foo/0.1@user/testing", "foo/0.2@user/testing"
'''
        files = {"conanfile.py": conanfile}
        client.save(files)
        error = client.run("install . --build", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Error while initializing requirements. Duplicated requirement",
                      client.user_io.out)
