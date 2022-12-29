import os
import unittest
from collections import OrderedDict

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import (TestClient, TestServer, NO_SETTINGS_PACKAGE_ID, TurboTestClient,
                                     GenConanfile)
from conans.util.files import load


class DownloadTest(unittest.TestCase):

    def test_download_recipe(self):
        client = TurboTestClient(default_server_user={"lasote": "pass"})
        # Test download of the recipe only
        conanfile = str(GenConanfile().with_name("pkg").with_version("0.1"))
        ref = ConanFileReference.loads("pkg/0.1@lasote/stable")
        client.create(ref, conanfile)
        client.upload_all(ref)
        client.remove_all()

        client.run("download pkg/0.1@lasote/stable --recipe")

        self.assertIn("Downloading conanfile.py", client.out)
        self.assertNotIn("Downloading conan_package.tgz", client.out)
        export = client.cache.package_layout(ref).export()
        self.assertTrue(os.path.exists(os.path.join(export, "conanfile.py")))
        self.assertEqual(conanfile, load(os.path.join(export, "conanfile.py")))
        conan = client.cache.package_layout(ref).base_folder()
        self.assertFalse(os.path.exists(os.path.join(conan, "package")))

    def test_download_with_sources(self):
        server = TestServer()
        servers = OrderedDict()
        servers["default"] = server
        servers["other"] = TestServer()

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
        client.run("upload pkg/0.1@lasote/stable")
        client.run("remove pkg/0.1@lasote/stable -f")

        client.run("download pkg/0.1@lasote/stable")
        self.assertIn("Downloading conan_sources.tgz", client.out)
        source = client.cache.package_layout(ref).export_sources()
        self.assertEqual("myfile.h", load(os.path.join(source, "file.h")))
        self.assertEqual("C++code", load(os.path.join(source, "otherfile.cpp")))

    def test_download_reference_without_packages(self):
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": GenConanfile().with_name("pkg").with_version("0.1")})
        client.run("export . user/stable")
        client.run("upload pkg/0.1@user/stable")
        client.run("remove pkg/0.1@user/stable -f")

        client.run("download pkg/0.1@user/stable")
        # Check 'No remote binary packages found' warning
        self.assertIn("WARN: No remote binary packages found in remote", client.out)
        # Check at least conanfile.py is downloaded
        ref = ConanFileReference.loads("pkg/0.1@user/stable")
        self.assertTrue(os.path.exists(client.cache.package_layout(ref).conanfile()))

    def test_download_reference_with_packages(self):
        server = TestServer()
        servers = {"default": server}

        client = TurboTestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    name = "pkg"
    version = "0.1"
    settings = "os"
"""
        ref = ConanFileReference.loads("pkg/0.1@lasote/stable")

        client.create(ref, conanfile)
        client.upload_all(ref)
        client.remove_all()

        client.run("download pkg/0.1@lasote/stable")

        package_layout = client.cache.package_layout(ref)

        package_folder = os.path.join(package_layout.packages(),
                                      os.listdir(package_layout.packages())[0])
        # Check not 'No remote binary packages found' warning
        self.assertNotIn("WARN: No remote binary packages found in remote", client.out)
        # Check at conanfile.py is downloaded
        self.assertTrue(os.path.exists(package_layout.conanfile()))
        # Check package folder created
        self.assertTrue(os.path.exists(package_folder))

    def test_download_wrong_id(self):
        client = TurboTestClient(servers={"default": TestServer()},
                                 users={"default": [("lasote", "mypass")]})

        ref = ConanFileReference.loads("pkg/0.1@lasote/stable")
        client.export(ref)
        client.upload_all(ref)
        client.remove_all()

        client.run("download pkg/0.1@lasote/stable:wrong", assert_error=True)
        self.assertIn("ERROR: Binary package not found: 'pkg/0.1@lasote/stable:wrong'",
                      client.out)

    def test_download_pattern(self):
        client = TestClient()
        client.run("download pkg/*@user/channel", assert_error=True)
        self.assertIn("Provide a valid full reference without wildcards", client.out)

    def test_download_full_reference(self):
        server = TestServer()
        servers = {"default": server}

        client = TurboTestClient(servers=servers, users={"default": [("lasote", "mypass")]})

        ref = ConanFileReference.loads("pkg/0.1@lasote/stable")
        client.create(ref)
        client.upload_all(ref)
        client.remove_all()

        client.run("download pkg/0.1@lasote/stable:{}".format(NO_SETTINGS_PACKAGE_ID))

        package_layout = client.cache.package_layout(ref)
        package_folder = os.path.join(package_layout.packages(),
                                      os.listdir(package_layout.packages())[0])
        # Check not 'No remote binary packages found' warning
        self.assertNotIn("WARN: No remote binary packages found in remote", client.out)
        # Check at conanfile.py is downloaded
        self.assertTrue(os.path.exists(package_layout.conanfile()))
        # Check package folder created
        self.assertTrue(os.path.exists(package_folder))

    def test_download_with_full_reference_and_p(self):
        client = TestClient()
        client.run("download pkg/0.1@user/channel:{package_id} -p {package_id}".
                   format(package_id="dupqipa4tog2ju3pncpnrzbim1fgd09g"),
                   assert_error=True)
        self.assertIn("Use a full package reference (preferred) or the `--package`"
                      " command argument, but not both.", client.out)

    def test_download_with_package_and_recipe_args(self):
        client = TestClient()
        client.run("download eigen/3.3.4@conan/stable --recipe --package fake_id",
                   assert_error=True)

        self.assertIn("ERROR: recipe parameter cannot be used together with package", client.out)

    def test_download_package_argument(self):
        server = TestServer()
        servers = {"default": server}

        client = TurboTestClient(servers=servers, users={"default": [("lasote", "mypass")]})

        ref = ConanFileReference.loads("pkg/0.1@lasote/stable")
        client.create(ref)
        client.upload_all(ref)
        client.remove_all()

        client.run("download pkg/0.1@lasote/stable -p {}".format(NO_SETTINGS_PACKAGE_ID))

        package_layout = client.cache.package_layout(ref)
        package_folder = os.path.join(package_layout.packages(),
                                      os.listdir(package_layout.packages())[0])
        # Check not 'No remote binary packages found' warning
        self.assertNotIn("WARN: No remote binary packages found in remote", client.out)
        # Check at conanfile.py is downloaded
        self.assertTrue(os.path.exists(package_layout.conanfile()))
        # Check package folder created
        self.assertTrue(os.path.exists(package_folder))

    def test_download_not_found_reference(self):
        server = TestServer()
        servers = {"default": server}
        client = TurboTestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        client.run("download pkg/0.1@lasote/stable", assert_error=True)
        self.assertIn("ERROR: Recipe not found: 'pkg/0.1@lasote/stable'", client.out)

    def test_no_user_channel(self):
        # https://github.com/conan-io/conan/issues/6009
        server = TestServer(users={"user": "password"}, write_permissions=[("*/*@*/*", "*")])
        client = TestClient(servers={"default": server}, users={"default": [("user", "password")]})
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . pkg/1.0@")
        client.run("upload * --all --confirm")
        client.run("remove * -f")

        client.run("download pkg/1.0:{}".format(NO_SETTINGS_PACKAGE_ID))
        self.assertIn("pkg/1.0: Downloading pkg/1.0:%s" % NO_SETTINGS_PACKAGE_ID, client.out)
        self.assertIn("pkg/1.0: Package installed %s" % NO_SETTINGS_PACKAGE_ID, client.out)

        # All
        client.run("remove * -f")
        client.run("download pkg/1.0@")
        self.assertIn("pkg/1.0: Downloading pkg/1.0:%s" % NO_SETTINGS_PACKAGE_ID, client.out)
        self.assertIn("pkg/1.0: Package installed %s" % NO_SETTINGS_PACKAGE_ID, client.out)
