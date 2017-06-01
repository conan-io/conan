import unittest
from conans.test.utils.tools import TestClient
from conans.model.ref import ConanFileReference
import os


class NoCopySourceTest(unittest.TestCase):

    def test_basic(self):
        conanfile = '''
from conans import ConanFile
from conans.util.files import save, load
import os

class ConanFileToolsTest(ConanFile):
    name = "Pkg"
    version = "0.1"
    exports_sources = "*"
    no_copy_source = True

    def build(self):
        self.output.info("Source files: %s" % load(os.path.join(self.source_folder, "file.h")))
        save("myartifact.lib", "artifact contents!")

    def package(self):
        self.copy("*")
'''

        client = TestClient()
        client.save({"conanfile.py": conanfile,
                     "file.h": "myfile.h contents"})
        client.run("export lasote/testing")
        client.run("install Pkg/0.1@lasote/testing --build")
        self.assertIn("Source files: myfile.h contents", client.user_io.out)
        ref = ConanFileReference.loads("Pkg/0.1@lasote/testing")

        builds = client.client_cache.builds(ref)
        pid = os.listdir(builds)[0]
        build_folder = os.path.join(builds, pid)
        self.assertNotIn("file.h", os.listdir(build_folder))
        packages = client.client_cache.packages(ref)
        package_folder = os.path.join(packages, pid)
        self.assertIn("file.h", os.listdir(package_folder))
        self.assertIn("myartifact.lib", os.listdir(package_folder))
