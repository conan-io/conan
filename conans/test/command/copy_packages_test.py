import unittest
from conans.test.utils.tools import TestClient
import os
from conans.model.ref import ConanFileReference


class CopyPackagesTest(unittest.TestCase):

    def test_copy_command(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    settings = "os"
"""
        client.save({"conanfile.py": conanfile})
        client.run("export . Hello0/0.1@lasote/stable")
        client.run("install Hello0/0.1@lasote/stable -s os=Windows --build missing")
        client.run("install Hello0/0.1@lasote/stable -s os=Linux --build missing")
        client.run("install Hello0/0.1@lasote/stable -s os=Macos --build missing")

        # Copy all packages
        client.run("copy Hello0/0.1@lasote/stable pepe/testing --all")
        pkgdir = client.paths.packages(ConanFileReference.loads("Hello0/0.1@pepe/testing"))
        packages = os.listdir(pkgdir)
        self.assertEquals(len(packages), 3)

        # Copy just one
        client.run("copy Hello0/0.1@lasote/stable pepe/stable -p %s" % packages[0])
        pkgdir = client.paths.packages(ConanFileReference.loads("Hello0/0.1@pepe/stable"))
        packages = os.listdir(pkgdir)
        self.assertEquals(len(packages), 1)

        # Force
        client.run("copy Hello0/0.1@lasote/stable pepe/stable -p %s --force" % packages[0])
        packages = os.listdir(pkgdir)
        self.assertEquals(len(packages), 1)

        # Copy only recipe
        client.run("copy Hello0/0.1@lasote/stable pepe/alpha", ignore_error=True)
        pkgdir = client.paths.packages(ConanFileReference.loads("Hello0/0.1@pepe/alpha"))
        self.assertFalse(os.path.exists(pkgdir))
