import os
import unittest
from conans.test.utils.tools import TestClient
from conans.paths import CONANFILE


conanfile = """
from conans import ConanFile, tools

class AConan(ConanFile):
    name = "Hello0"
    version = "0.1"

    def build(self):
        self.output.warn("build() IN LOCAL CACHE=> %s" % str(self.in_local_cache))
        
    def package(self):
        self.output.warn("package() IN LOCAL CACHE=> %s" % str(self.in_local_cache))

"""


class InLocalCacheTest(unittest.TestCase):

    def test_in_local_cache_flag(self):
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("export . lasote/stable")
        client.run("install Hello0/0.1@lasote/stable --build missing")
        self.assertIn("build() IN LOCAL CACHE=> True", client.user_io.out)
        self.assertIn("package() IN LOCAL CACHE=> True", client.user_io.out)

        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("install .")
        client.run("build .")
        self.assertIn("build() IN LOCAL CACHE=> False", client.user_io.out)

        pack_folder = os.path.join(client.current_folder, "package")
        os.mkdir(pack_folder)
        client.current_folder = pack_folder
        client.run("package .. --build-folder ..")
        self.assertIn("package() IN LOCAL CACHE=> False", client.user_io.out)

        # Confirm that we have the flag depending on the recipe too
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("export . lasote/stable")
        conanfile_reuse = """
from conans import ConanFile, tools

class OtherConan(ConanFile):
    name = "Hello1"
    version = "0.1"
    requires = "Hello0/0.1@lasote/stable"

    def build(self):
        pass
"""
        client.save({CONANFILE: conanfile_reuse}, clean_first=True)
        client.run("install . --build")
        self.assertIn("build() IN LOCAL CACHE=> True", client.user_io.out)
        self.assertIn("package() IN LOCAL CACHE=> True", client.user_io.out)
        client.run("export . lasote/stable")
        client.run("install Hello1/0.1@lasote/stable --build")
        self.assertIn("build() IN LOCAL CACHE=> True", client.user_io.out)
        self.assertIn("package() IN LOCAL CACHE=> True", client.user_io.out)


