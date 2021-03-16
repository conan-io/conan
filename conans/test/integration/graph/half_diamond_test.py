import os
import unittest

from conans.model.ref import ConanFileReference
from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient, GenConanfile
from conans.util.files import load


class HalfDiamondTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()

    def _export(self, name, deps=None, export=True):

        conanfile = GenConanfile().with_name(name).with_version("0.1")\
                                  .with_option("potato", [True, False])\
                                  .with_default_option("potato", True)
        if deps:
            for dep in deps:
                ref = ConanFileReference.loads(dep)
                conanfile = conanfile.with_require(ref)

        conanfile = str(conanfile) + """
    def config_options(self):
        del self.options.potato
"""
        self.client.save({CONANFILE: conanfile}, clean_first=True)
        if export:
            self.client.run("export . lasote/stable")

    def test_reuse(self):
        self._export("Hello0")
        self._export("Hello1", ["Hello0/0.1@lasote/stable"])
        self._export("Hello2", ["Hello1/0.1@lasote/stable", "Hello0/0.1@lasote/stable"])
        self._export("Hello3", ["Hello2/0.1@lasote/stable"], export=False)

        self.client.run("install . --build missing")
        self.assertIn("conanfile.py (Hello3/0.1): Generated conaninfo.txt",
                      self.client.out)

    def test_check_duplicated_full_requires(self):
        self._export("Hello0")
        self._export("Hello1", ["Hello0/0.1@lasote/stable"])
        self._export("Hello2", ["Hello1/0.1@lasote/stable", "Hello0/0.1@lasote/stable"],
                     export=False)

        self.client.run("install . --build missing")
        self.assertIn("conanfile.py (Hello2/0.1): Generated conaninfo.txt",
                      self.client.out)
        conaninfo = self.client.load("conaninfo.txt")
        self.assertEqual(1, conaninfo.count("Hello0/0.1@lasote/stable"))
