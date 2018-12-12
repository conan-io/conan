import os
import unittest

from conans.test.utils.tools import TestClient, TestServer
from conans.util.files import load


class CIGraphLockRevisionsTest(unittest.TestCase):
    def setUp(self):
        os.environ["CONAN_API_V2_BLOCKED"] = "False"
        os.environ["CONAN_CLIENT_REVISIONS_ENABLED"] = "True"

    def lock_revision_test(self):
        # locking a version range
        client = TestClient(servers={"default": TestServer()},
                            users={"default": [("lasote", "mypass")]})
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    def configure(self):
        self.output.info("I am %s")
"""
        client.save({"conanfile.py": conanfile % "Revision1!"})
        client.run("create . PkgA/0.1@lasote/channel")
        client.run("upload PkgA* --all --confirm")

        # Use a consumer with a version range
        consumer = """from conans import ConanFile
class Pkg(ConanFile):
    requires = "PkgA/0.1@lasote/channel"
"""
        client.save({"conanfile.py": consumer})
        client.run("install . --output-lock=default.lock")
        self.assertIn("PkgA/0.1@lasote/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9",
                      client.out)
        lock_file = load(os.path.join(client.current_folder, "default.lock"))
        self.assertIn("PkgA/0.1@lasote/channel", lock_file)

        # If we create a new PkgA version
        client.save({"conanfile.py": conanfile % "Revision2!"})
        # Will overwrite in cache previous revision
        client.run("create . PkgA/0.1@lasote/channel")
        self.assertIn("PkgA/0.1@lasote/channel: I am Revision2!", client.out)

        # Normal install will use it
        client.save({"conanfile.py": consumer})
        client.run("install .")
        self.assertIn("PkgA/0.1@lasote/channel: I am Revision2!", client.out)

        # Locked install will use PkgA/0.1
        client.run("install . --input-lock=default.lock -g=cmake")
        self.assertIn("PkgA/0.1@lasote/channel: I am Revision1!", client.out)
        self.assertNotIn("Revision2!", client.out)

        # Info also works
        client.run("info . --input-lock=default.lock")
        self.assertIn("PkgA/0.1@lasote/channel: I am Revision1!", client.out)
        self.assertNotIn("Revision2!", client.out)
