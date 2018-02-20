import unittest
from conans.test.utils.tools import TestClient
from conans.paths import CONANFILE
from conans.util.files import load
import os
from conans.test.utils.conanfile import TestConanFile


class HalfDiamondTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()

    def _export(self, name, deps=None, export=True):

        conanfile = TestConanFile(name, "0.1", requires=deps,
                                  options={"potato": [True, False]},
                                  default_options="potato=True")
        conanfile = str(conanfile) + """
    def config_options(self):
        del self.options.potato
"""
        self.client.save({CONANFILE: conanfile}, clean_first=True)
        if export:
            self.client.run("export . lasote/stable")

    def reuse_test(self):
        self._export("Hello0")
        self._export("Hello1", ["Hello0/0.1@lasote/stable"])
        self._export("Hello2", ["Hello1/0.1@lasote/stable", "Hello0/0.1@lasote/stable"])
        self._export("Hello3", ["Hello2/0.1@lasote/stable"], export=False)

        self.client.run("install . --build missing")
        self.assertIn("PROJECT: Generated conaninfo.txt", self.client.user_io.out)

    def check_duplicated_full_requires_test(self):
        self._export("Hello0")
        self._export("Hello1", ["Hello0/0.1@lasote/stable"])
        self._export("Hello2", ["Hello1/0.1@lasote/stable", "Hello0/0.1@lasote/stable"],
                     export=False)

        self.client.run("install . --build missing")
        self.assertIn("PROJECT: Generated conaninfo.txt", self.client.user_io.out)
        conaninfo = load(os.path.join(self.client.current_folder, "conaninfo.txt"))
        self.assertEqual(1, conaninfo.count("Hello0/0.1@lasote/stable"))
