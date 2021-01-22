import os
import unittest
import textwrap

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient, TestServer
from conans.util.files import load
from parameterized.parameterized import parameterized


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
        pkgdir = client.cache.package_layout(ConanFileReference.loads("Hello0/0.1@pepe/testing")).packages()
        packages = os.listdir(pkgdir)
        self.assertEqual(len(packages), 3)

        # Copy just one with --package argument
        client.run("copy Hello0/0.1@lasote/stable pepe/beta -p %s" % packages[0])
        pkgdir = client.cache.package_layout(ConanFileReference.loads("Hello0/0.1@pepe/beta")).packages()
        packages = os.listdir(pkgdir)
        self.assertEqual(len(packages), 1)

        # Copy just one with full reference
        client.run("copy Hello0/0.1@lasote/stable:%s pepe/stable" % packages[0])
        pkgdir = client.cache.package_layout(ConanFileReference.loads("Hello0/0.1@pepe/stable")).packages()
        packages = os.listdir(pkgdir)
        self.assertEqual(len(packages), 1)

        # Force
        client.run("copy Hello0/0.1@lasote/stable pepe/stable -p %s --force" % packages[0])
        packages = os.listdir(pkgdir)
        self.assertEqual(len(packages), 1)

        # Copy only recipe
        client.run("copy Hello0/0.1@lasote/stable pepe/alpha")
        pkgdir = client.cache.package_layout(ConanFileReference.loads("Hello0/0.1@pepe/alpha")).packages()
        self.assertFalse(os.path.exists(pkgdir))

    @parameterized.expand([(True, ), (False,)])
    def test_copy_exports_sources_with_revision_command(self, revision_enabled):
        server = TestServer()
        client = TestClient(servers={"default": server},
                            users={"default": [("lasote", "mypass")]},
                            revisions_enabled=True)

        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    exports_sources = "*"
"""

        client.save({"conanfile.py": conanfile,
                     "myfile.txt": "my data!"})
        # Not necessary to create binary packages, faster test
        client.run("export . pkg/0.1@lasote/stable")
        client.run("upload pkg/0.1@lasote/stable")

        client2 = TestClient(servers={"default": server},
                             revisions_enabled=revision_enabled)
        # To install the recipe without needing to install the binary packages
        client2.run("info pkg/0.1@lasote/stable")

        # Now the other client uploads a new revision
        client.save({"conanfile.py": conanfile + "# Recipe revision 2",
                     "myfile.txt": "my data rev2!"})
        client.run("export . pkg/0.1@lasote/stable")
        client.run("upload pkg/0.1@lasote/stable")

        client2.run("copy pkg/0.1@lasote/stable other/channel --all")
        self.assertIn("Downloading conan_sources.tgz", client2.out)

        ref = ConanFileReference.loads("pkg/0.1@lasote/stable")
        conanfile = load(client2.cache.package_layout(ref).conanfile())
        self.assertNotIn("# Recipe revision 2", conanfile)
        data = load(os.path.join(client2.cache.package_layout(ref).export_sources(), "myfile.txt"))
        # With revisions, it work, it fetches the correct one
        if revision_enabled:
            self.assertIn("my data!", data)
        else:
            self.assertIn("my data rev2!", data)

    def test_full_reference_with_all_argument(self):
        client = TestClient()
        client.run("copy pkg/0.1@user/channel:{} other/channel --all".format("mimic"),
                   assert_error=True)
        self.assertIn("'--all' argument cannot be used together with full reference", client.out)

    def test_copy_with_p_and_all(self):
        client = TestClient()
        client.run("copy pkg/0.1@user/channel other/channel -p {} --all".format("mimic"),
                   assert_error=True)
        self.assertIn("Cannot specify both --all and --package", client.out)

    def test_copy_full_reference(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                settings = "os"
        """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("export . pkg/0.1@user/channel")
        client.run("copy pkg/0.1@user/channel pkg/0.1@other/branch", assert_error=True)
        self.assertIn("Destination must contain user/channel only.", client.out)
