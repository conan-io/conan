import unittest
from conans.test.utils.tools import TestClient, TestServer
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.paths import is_case_insensitive_os, CONANFILE


conanfile = '''
from conans import ConanFile

class ConanLib(ConanFile):
    name = "Hello0"
    version = "0.1"

    def source(self):
        self.output.info("Running source!")
'''


class CaseSensitiveTest(unittest.TestCase):

    def install_test(self):
        test_server = TestServer()
        servers = {"default": test_server}
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})

        files = cpp_hello_conan_files("Hello0", "0.1", build=False)
        client.save(files)
        client.run("export . lasote/stable")

        client.run("install Hello0/0.1@lasote/stable --build missing")
        client.run("upload  Hello0/0.1@lasote/stable --all")

        # If we try to install the same package with --build oudated it's already ok
        files = cpp_hello_conan_files("Hello1", "0.1", deps=["hello0/0.1@lasote/stable"],
                                      build=False)
        client.save(files)
        error = client.run("install .", ignore_error=True)
        self._check(error, client)

    def _check(self, error, client):
        self.assertTrue(error)
        if is_case_insensitive_os():
            self.assertIn("case incompatible 'Hello0'", client.user_io.out)
        else:
            self.assertNotIn("case incompatible 'Hello0'", client.user_io.out)

    def install_same_test(self):
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("export . lasote/stable")
        error = client.run("install hello0/0.1@lasote/stable --build=missing", ignore_error=True)
        self._check(error, client)

    def imports_test(self):
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("export . lasote/stable")
        client.run("install Hello0/0.1@lasote/stable --build=missing")
        error = client.run("imports hello0/0.1@lasote/stable", ignore_error=True)
        self.assertTrue(error)
        # Reference interpreted as a path, so no valid path
        self.assertIn("Parameter 'path' cannot be a reference", client.out)

    def package_test(self):
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("export . lasote/stable")
        client.run("install Hello0/0.1@lasote/stable --build=missing")
        error = client.run("export-pkg . hello0/0.1@lasote/stable", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Package recipe exported with name hello0!=Hello0", client.out)

    def copy_test(self):
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("export . lasote/stable")
        client.run("install Hello0/0.1@lasote/stable --build=missing")
        error = client.run("copy hello0/0.1@lasote/stable otheruser/testing", ignore_error=True)
        self._check(error, client)
