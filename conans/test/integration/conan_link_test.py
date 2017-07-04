import unittest
from conans.test.utils.tools import TestClient, TestServer
from conans.util.files import load
import os


class ConanLinkTest(unittest.TestCase):

    def setUp(self):
        test_server = TestServer()
        self.servers = {"default": test_server}

    def basic_test(self):
        client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        conanfile = """from conans import ConanFile

class TestConan(ConanFile):
    name = "Hello"
    version = "0.1"
    """
        client.save({"conanfile.py": conanfile})
        client.run("export lasote/channel")
        conanfile_link = """from conans import ConanFile

class TestConan(ConanFile):
    name = "Hello"
    version = "0.X"
    conan_link = "Hello/0.1@lasote/channel"
    """
        client.save({"conanfile.py": conanfile_link}, clean_first=True)
        client.run("export lasote/channel")
        conanfile_chat = """from conans import ConanFile

class TestConan(ConanFile):
    name = "Chat"
    version = "1.0"
    requires = "Hello/0.X@lasote/channel"
    """
        client.save({"conanfile.py": conanfile_chat}, clean_first=True)
        client.run("export lasote/channel")
        client.save({"conanfile.txt": "[requires]\nChat/1.0@lasote/channel"}, clean_first=True)

        client.run("install --build=missing")

        self.assertIn("Hello/0.1@lasote/channel from local", client.user_io.out)
        self.assertNotIn("Hello/0.X", client.user_io.out)
        conaninfo = load(os.path.join(client.current_folder, "conaninfo.txt"))
        self.assertIn("Hello/0.1@lasote/channel", conaninfo)
        self.assertNotIn("Hello/0.X", conaninfo)

        client.run('upload "*" --all --confirm')
        client.run('remove "*" -f')

        client.run("install")
        self.assertIn("Hello/0.1@lasote/channel from default", client.user_io.out)
        self.assertNotIn("Hello/0.X@lasote/channel from", client.user_io.out)
