import unittest
from conans.test.utils.tools import TestClient, TestServer
from conans.util.files import load
import os


class ConanAliasTest(unittest.TestCase):

    def alias_bug_test(self):
        # https://github.com/conan-io/conan/issues/2252
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    pass
"""
        client.save({"conanfile.py": conanfile})
        client.run("create . Pkg/0.1@user/testing")
        client.run("alias Pkg/latest@user/testing Pkg/0.1@user/testing")
        dep_conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    requires = "Pkg/latest@user/testing"
"""
        client.save({"conanfile.py": dep_conanfile})
        client.run("create . Pkg1/0.1@user/testing")
        client.run("create . Pkg2/0.1@user/testing")

        root_conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    requires = "Pkg1/0.1@user/testing", "Pkg2/0.1@user/testing"
"""
        client.save({"conanfile.py": root_conanfile})
        client.run("create . PkgRoot/0.1@user/testing")
        self.assertNotIn("Pkg/latest@user/testing", client.out)
        self.assertIn("Pkg/0.1@user/testing: Already installed!", client.out)
        self.assertIn("Pkg1/0.1@user/testing: Already installed!", client.out)
        self.assertIn("Pkg2/0.1@user/testing: Already installed!", client.out)

    def transitive_alias_test(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    pass
"""
        client.save({"conanfile.py": conanfile})
        client.run("create . Pkg/0.1@user/testing")
        client.run("alias Pkg/latest@user/testing Pkg/0.1@user/testing")
        client.run("alias Pkg/superlatest@user/testing Pkg/latest@user/testing")
        client.run("alias Pkg/megalatest@user/testing Pkg/superlatest@user/testing")
        dep_conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    requires = "Pkg/megalatest@user/testing"
"""
        client.save({"conanfile.py": dep_conanfile})
        client.run("create . Consumer/0.1@user/testing")
        self.assertIn("Pkg/0.1@user/testing: Already installed!", client.out)
        self.assertNotIn("latest", client.out)

    def repeated_alias_test(self):
        client = TestClient()
        client.run("alias Hello/0.X@lasote/channel Hello/0.1@lasote/channel")
        client.run("alias Hello/0.X@lasote/channel Hello/0.2@lasote/channel")
        client.run("alias Hello/0.X@lasote/channel Hello/0.3@lasote/channel")

    def basic_test(self):
        test_server = TestServer()
        servers = {"default": test_server}
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        for i in (1, 2):
            conanfile = """from conans import ConanFile

class TestConan(ConanFile):
    name = "Hello"
    version = "0.%s"
    """ % i
            client.save({"conanfile.py": conanfile})
            client.run("export . lasote/channel")

        client.run("alias Hello/0.X@lasote/channel Hello/0.1@lasote/channel")
        conanfile_chat = """from conans import ConanFile

class TestConan(ConanFile):
    name = "Chat"
    version = "1.0"
    requires = "Hello/0.X@lasote/channel"
    """
        client.save({"conanfile.py": conanfile_chat}, clean_first=True)
        client.run("export . lasote/channel")
        client.save({"conanfile.txt": "[requires]\nChat/1.0@lasote/channel"}, clean_first=True)

        client.run("install . --build=missing")

        self.assertIn("Hello/0.1@lasote/channel from local", client.user_io.out)
        self.assertNotIn("Hello/0.X", client.user_io.out)
        conaninfo = load(os.path.join(client.current_folder, "conaninfo.txt"))
        self.assertIn("Hello/0.1@lasote/channel", conaninfo)
        self.assertNotIn("Hello/0.X", conaninfo)

        client.run('upload "*" --all --confirm')
        client.run('remove "*" -f')

        client.run("install .")
        self.assertIn("Hello/0.1@lasote/channel from 'default'", client.user_io.out)
        self.assertNotIn("Hello/0.X@lasote/channel from", client.user_io.out)

        client.run("alias Hello/0.X@lasote/channel Hello/0.2@lasote/channel")
        client.run("install . --build=missing")
        self.assertIn("Hello/0.2", client.user_io.out)
        self.assertNotIn("Hello/0.1", client.user_io.out)
