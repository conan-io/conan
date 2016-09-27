import unittest
from conans.test.tools import TestClient
from conans.paths import CONANFILE


class HalfDiamondTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()

    def _export(self, name, deps=None, export=True):
        deps = ", ".join(['"%s"' % d for d in deps or []]) or '""'
        conanfile = """
from conans import ConanFile, CMake
import os

class HelloReuseConan(ConanFile):
    name = "%s"
    version = "0.1"
    requires = %s
    options = {"potato": [True, False]}
    default_options = "potato=True"

    def config_options(self):
        del self.options.potato
""" % (name, deps)
        files = {CONANFILE: conanfile}
        self.client.save(files, clean_first=True)
        if export:
            self.client.run("export lasote/stable")

    def reuse_test(self):
        self._export("Hello0")
        self._export("Hello1", ["Hello0/0.1@lasote/stable"])
        self._export("Hello2", ["Hello1/0.1@lasote/stable", "Hello0/0.1@lasote/stable"])
        self._export("Hello3", ["Hello2/0.1@lasote/stable"], export=False)

        self.client.run("install . --build missing")
        self.assertIn("PROJECT: Generated conaninfo.txt", self.client.user_io.out)
