import unittest
import os
from conans.test.utils.tools import TestClient, TestServer
from conans.model.ref import ConanFileReference
from conans.util.files import load


class DownloadTest(unittest.TestCase):

    def download_recipe_test(self):
        server = TestServer()
        servers = {"default": server}
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})

        # Test argument --package and --recipe cannot be together
        error = client.run("download eigen/3.3.4@conan/stable --recipe --package fake_id",
                           ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: recipe parameter cannot be used together with package", client.out)

        # Test download of the recipe only
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    name = "pkg"
    version = "0.1"
    exports_sources = "*"
"""
        client.save({"conanfile.py": conanfile,
                     "file.h": "myfile.h"})
        client.run("create . lasote/stable")
        ref = ConanFileReference.loads("pkg/0.1@lasote/stable")
        self.assertTrue(os.path.exists(client.paths.conanfile(ref)))
        conan = client.client_cache.conan(ref)
        self.assertTrue(os.path.exists(os.path.join(conan, "package")))
        client.run("upload pkg/0.1@lasote/stable --all")
        client.run("remove pkg/0.1@lasote/stable -f")
        self.assertFalse(os.path.exists(client.paths.export(ref)))
        client.run("download pkg/0.1@lasote/stable --recipe")

        self.assertIn("Downloading conanfile.py", client.out)
        self.assertNotIn("Downloading conan_sources.tgz", client.out)
        self.assertNotIn("Downloading conan_package.tgz", client.out)
        export = client.client_cache.export(ref)
        self.assertTrue(os.path.exists(os.path.join(export, "conanfile.py")))
        self.assertEqual(conanfile, load(os.path.join(export, "conanfile.py")))
        source = client.client_cache.export_sources(ref)
        self.assertFalse(os.path.exists(os.path.join(source, "file.h")))
        conan = client.client_cache.conan(ref)
        self.assertFalse(os.path.exists(os.path.join(conan, "package")))

    def download_with_sources_test(self):
        server = TestServer()
        servers = {"default": server,
                   "other": TestServer()}

        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")],
                                                    "other": [("lasote", "mypass")]})
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    name = "pkg"
    version = "0.1"
    exports_sources = "*"
"""
        client.save({"conanfile.py": conanfile,
                     "file.h": "myfile.h",
                     "otherfile.cpp": "C++code"})
        client.run("export . lasote/stable")

        ref = ConanFileReference.loads("pkg/0.1@lasote/stable")
        self.assertTrue(os.path.exists(client.paths.conanfile(ref)))

        client.run("upload pkg/0.1@lasote/stable")
        client.run("remove pkg/0.1@lasote/stable -f")
        self.assertFalse(os.path.exists(client.paths.export(ref)))

        client.run("download pkg/0.1@lasote/stable")
        self.assertIn("Downloading conan_sources.tgz", client.out)
        source = client.client_cache.export_sources(ref)
        self.assertEqual("myfile.h", load(os.path.join(source, "file.h")))
        self.assertEqual("C++code", load(os.path.join(source, "otherfile.cpp")))

    def download_reference_without_packages_test(self):
        server = TestServer()
        servers = {"default": server}

        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    name = "pkg"
    version = "0.1"
"""
        client.save({"conanfile.py": conanfile})
        client.run("export . lasote/stable")

        ref = ConanFileReference.loads("pkg/0.1@lasote/stable")
        self.assertTrue(os.path.exists(client.paths.conanfile(ref)))

        client.run("upload pkg/0.1@lasote/stable")
        client.run("remove pkg/0.1@lasote/stable -f")
        self.assertFalse(os.path.exists(client.paths.export(ref)))

        client.run("download pkg/0.1@lasote/stable")
        # Check 'No remote binary packages found' warning
        self.assertTrue("WARN: No remote binary packages found in remote", client.out)
        # Check at least conanfile.py is downloaded
        self.assertTrue(os.path.exists(client.paths.conanfile(ref)))

    def download_reference_with_packages_test(self):
        server = TestServer()
        servers = {"default": server}

        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    name = "pkg"
    version = "0.1"
    settings = "os"
"""

        client.save({"conanfile.py": conanfile})
        client.run("create . lasote/stable")

        ref = ConanFileReference.loads("pkg/0.1@lasote/stable")
        self.assertTrue(os.path.exists(client.paths.conanfile(ref)))

        package_folder = os.path.join(client.paths.conan(ref), "package", os.listdir(client.paths.packages(ref))[0])

        client.run("upload pkg/0.1@lasote/stable --all")
        client.run("remove pkg/0.1@lasote/stable -f")
        self.assertFalse(os.path.exists(client.paths.export(ref)))

        client.run("download pkg/0.1@lasote/stable")

        # Check not 'No remote binary packages found' warning
        self.assertNotIn("WARN: No remote binary packages found in remote", client.out)
        # Check at conanfile.py is downloaded
        self.assertTrue(os.path.exists(client.paths.conanfile(ref)))
        # Check package folder created
        self.assertTrue(os.path.exists(package_folder))

    def test_download_wrong_id(self):
        client = TestClient(servers={"default": TestServer()},
                            users={"default": [("lasote", "mypass")]})
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    pass
"""
        client.save({"conanfile.py": conanfile})
        client.run("export . pkg/0.1@lasote/stable")
        client.run("upload pkg/0.1@lasote/stable")
        client.run("remove pkg/0.1@lasote/stable -f")

        error = client.run("download pkg/0.1@lasote/stable -p=wrong", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Package binary 'pkg/0.1@lasote/stable:wrong' not found in 'default'", client.out)
