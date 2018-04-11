import unittest
from conans.test.utils.tools import TestClient
from conans.model.ref import ConanFileReference
import os
import platform


class RMdirFailTest(unittest.TestCase):

    def fail_rmdir_test(self):
        if platform.system() != "Windows":
            return
        client = TestClient()
        conanfile = """from conans import ConanFile
class MyPkg(ConanFile):
    name = "MyPkg"
    version = "0.1"
"""
        client.save({"conanfile.py": conanfile})
        client.run("export . lasote/testing")
        client.run("install MyPkg/0.1@lasote/testing --build")
        ref = ConanFileReference.loads("MyPkg/0.1@lasote/testing")
        builds = client.client_cache.builds(ref)
        build_folder = os.listdir(builds)[0]
        build_folder = os.path.join(builds, build_folder)
        f = open(os.path.join(build_folder, "myfile"), "wb")
        f.write(b"Hello world")
        error = client.run("install MyPkg/0.1@lasote/testing --build", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Couldn't remove folder, might be busy or open",
                      client.user_io.out)