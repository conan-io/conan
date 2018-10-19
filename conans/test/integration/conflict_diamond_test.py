import unittest
from conans.test.utils.tools import TestClient
from conans.paths import CONANFILE


class ConflictDiamondTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()

    def _export(self, name, version, deps=None, export=True):
        deps = ", ".join(['"%s"' % d for d in deps or []]) or '""'
        conanfile = """
from conans import ConanFile, CMake
import os

class HelloReuseConan(ConanFile):
    name = "%s"
    version = "%s"
    requires = %s
""" % (name, version, deps)
        files = {CONANFILE: conanfile}
        self.client.save(files, clean_first=True)
        if export:
            self.client.run("export . lasote/stable")

    def reuse_test(self):
        self._export("Hello0", "0.1")
        self._export("Hello0", "0.2")
        self._export("Hello1", "0.1", ["Hello0/0.1@lasote/stable"])
        self._export("Hello2", "0.1", ["Hello0/0.2@lasote/stable"])
        self._export("Hello3", "0.1", ["Hello1/0.1@lasote/stable", "Hello2/0.1@lasote/stable"],
                     export=False)

        error = self.client.run("install . --build missing", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Conflict in Hello2/0.1@lasote/stable", self.client.user_io.out)
        self.assertNotIn("PROJECT: Generated conaninfo.txt", self.client.user_io.out)
