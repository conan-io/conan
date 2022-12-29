import platform
import textwrap
import unittest

import pytest

from conans.paths import CONANFILE
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, TestServer

conanfile = textwrap.dedent('''
    from conans import ConanFile

    class ConanLib(ConanFile):
        name = "Hello0"
        version = "0.1"

        def source(self):
            self.output.info("Running source!")
''')


@pytest.mark.skipif(platform.system() == 'Linux', reason="Only for case insensitive OS")
class CaseSensitiveTest(unittest.TestCase):

    def test_install(self):
        test_server = TestServer()
        servers = {"default": test_server}
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})

        client.save({"conanfile.py": GenConanfile("Hello0", "0.1")})
        client.run("create . lasote/stable")
        client.run("upload Hello0/0.1@lasote/stable --all")

        client.save({"conanfile.py": GenConanfile().with_requires("hello0/0.1@lasote/stable")})
        client.run("install .", assert_error=True)
        self.assertIn("found case incompatible recipe with name 'Hello0' in the cache", client.out)

    def test_install_same(self):
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("export . lasote/stable")
        client.run("install hello0/0.1@lasote/stable --build=missing", assert_error=True)
        self.assertIn("found case incompatible recipe with name 'Hello0' in the cache", client.out)

    def test_copy(self):
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("export . lasote/stable")
        client.run("install Hello0/0.1@lasote/stable --build=missing")
        client.run("copy hello0/0.1@lasote/stable otheruser/testing", assert_error=True)
        self.assertIn("found case incompatible recipe with name 'Hello0' in the cache", client.out)

    def test_remove(self):
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("export . lasote/stable")
        client.run("remove hello0/0.1@lasote/stable -f", assert_error=True)
        self.assertIn("found case incompatible recipe with name 'Hello0' in the cache", client.out)


class MismatchReference(unittest.TestCase):
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
