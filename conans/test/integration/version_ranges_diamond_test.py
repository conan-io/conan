import unittest
from conans.test.tools import TestClient
from conans.paths import CONANFILE
from conans.util.files import load
import os


class VersionRangesDiamondTest(unittest.TestCase):

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
            self.client.run("export lasote/stable")

    def reuse_test(self):
        self._export("Hello0", "0.1")
        self._export("Hello0", "0.2")
        self._export("Hello0", "0.3")
        self._export("Hello1", "0.1", ["Hello0/[>0.1,<0.3]@lasote/stable"])
        self._export("Hello2", "0.1", ["Hello0/[0.2]@lasote/stable"])
        self._export("Hello3", "0.1", ["Hello1/[>=0]@lasote/stable", "Hello2/[~=0]@lasote/stable"],
                     export=False)

        self.client.run("install . --build missing")
        self.assertIn("Version range '~=0' required by 'None' resolved to "
                      "'Hello2/0.1@lasote/stable'", self.client.user_io.out)
        self.assertIn("Version range '>0.1,<0.3' required by 'Hello1/0.1@lasote/stable' "
                      "resolved to 'Hello0/0.2@lasote/stable'", self.client.user_io.out)
        self.assertIn("Version range '0.2' required by 'Hello2/0.1@lasote/stable' resolved "
                      "to 'Hello0/0.2@lasote/stable'", self.client.user_io.out)
        self.assertNotIn("Conflict", self.client.user_io.out)
        self.assertIn("PROJECT: Generated conaninfo.txt", self.client.user_io.out)

        content = load(os.path.join(self.client.current_folder, "conaninfo.txt"))
        self.assertIn("Hello0/0.2@lasote/stable", content)
        self.assertIn("Hello1/0.1@lasote/stable", content)
        self.assertIn("Hello2/0.1@lasote/stable", content)
