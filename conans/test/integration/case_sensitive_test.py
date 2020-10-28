import unittest

from conans.paths import CONANFILE
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.test.utils.tools import TestClient, TestServer
from conans.client.cache.cache import is_case_insensitive_os

conanfile = '''
from conans import ConanFile

class ConanLib(ConanFile):
    name = "Hello0"
    version = "0.1"

    def source(self):
        self.output.info("Running source!")
'''


class CaseSensitiveTest(unittest.TestCase):

    def test_install(self):
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
        client.run("install .", assert_error=True)
        self._check(client)

    def _check(self, client):
        if is_case_insensitive_os():
            self.assertIn("case incompatible 'Hello0'", client.out)
        else:
            self.assertNotIn("case incompatible 'Hello0'", client.out)

    def test_install_same(self):
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("export . lasote/stable")
        client.run("install hello0/0.1@lasote/stable --build=missing", assert_error=True)
        self._check(client)

    def test_imports(self):
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("export . lasote/stable")
        client.run("install Hello0/0.1@lasote/stable --build=missing")
        client.run("imports hello0/0.1@lasote/stable", assert_error=True)
        # Reference interpreted as a path, so no valid path
        self.assertIn("Parameter 'path' cannot be a reference", client.out)

    def test_package(self):
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("export . lasote/stable")
        client.run("install Hello0/0.1@lasote/stable --build=missing")
        client.run("export-pkg . hello0/0.1@lasote/stable", assert_error=True)
        self.assertIn("ERROR: Package recipe with name hello0!=Hello0", client.out)

    def test_copy(self):
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("export . lasote/stable")
        client.run("install Hello0/0.1@lasote/stable --build=missing")
        client.run("copy hello0/0.1@lasote/stable otheruser/testing", assert_error=True)
        self._check(client)
