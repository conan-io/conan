import os
import unittest

from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient

conanfile = """
from conans import ConanFile, tools

class AConan(ConanFile):
    name = "hello0"
    version = "0.1"

    def build(self):
        self.output.warning("build() IN LOCAL CACHE=> %s" % str(self.in_local_cache))

    def package(self):
        self.output.warning("package() IN LOCAL CACHE=> %s" % str(self.in_local_cache))

"""


class InLocalCacheTest(unittest.TestCase):

    def test_in_local_cache_flag(self):
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("export . --user=lasote --channel=stable")
        client.run("install --reference=hello0/0.1@lasote/stable --build missing")
        self.assertIn("build() IN LOCAL CACHE=> True", client.out)
        self.assertIn("package() IN LOCAL CACHE=> True", client.out)

        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("install .")
        client.run("build .")
        self.assertIn("build() IN LOCAL CACHE=> False", client.out)

        pack_folder = os.path.join(client.current_folder, "package")
        os.mkdir(pack_folder)
        client.current_folder = pack_folder

        # Confirm that we have the flag depending on the recipe too
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("export . --user=lasote --channel=stable")
        conanfile_reuse = """
from conans import ConanFile, tools

class OtherConan(ConanFile):
    name = "hello1"
    version = "0.1"
    requires = "hello0/0.1@lasote/stable"

    def build(self):
        pass
"""
        client.save({CONANFILE: conanfile_reuse}, clean_first=True)
        client.run("install . --build")
        self.assertIn("build() IN LOCAL CACHE=> True", client.out)
        self.assertIn("package() IN LOCAL CACHE=> True", client.out)
        client.run("export . --user=lasote --channel=stable")
        client.run("install --reference=hello1/0.1@lasote/stable --build")
        self.assertIn("build() IN LOCAL CACHE=> True", client.out)
        self.assertIn("package() IN LOCAL CACHE=> True", client.out)
