import os
import unittest
from collections import OrderedDict

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import (TestClient, TestServer, NO_SETTINGS_PACKAGE_ID, TurboTestClient,
                                     GenConanfile)
from conans.util.env_reader import get_env
from conans.util.files import load


class DownloadTest(unittest.TestCase):

    def download_recipe_test(self):
        client = TurboTestClient(default_server_user={"lasote": "pass"})
        # Test download of the recipe only
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    name = "pkg"
    version = "0.1"
"""
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

    def download_with_sources_test(self):
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

        client.run("upload pkg/0.1@lasote/stable")
        client.run("remove pkg/0.1@lasote/stable -f")

        client.run("download pkg/0.1@lasote/stable")
        # Check 'No remote binary packages found' warning
        self.assertIn("WARN: No remote binary packages found in remote", client.out)
        # Check at least conanfile.py is downloaded
        self.assertTrue(os.path.exists(client.cache.package_layout(ref).conanfile()))

    def download_reference_with_packages_test(self):
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

    def download_full_reference_test(self):
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

    def download_package_argument_test(self):
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

    def download_not_found_reference_test(self):
        server = TestServer()
        servers = {"default": server}
        client = TurboTestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        client.run("download pkg/0.1@lasote/stable", assert_error=True)
        self.assertIn("ERROR: Recipe not found: 'pkg/0.1@lasote/stable'", client.out)

    def no_user_channel_test(self):
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

    @unittest.skipIf(get_env("TESTING_REVISIONS_ENABLED", False), "No sense with revs")
    def download_revs_disabled_with_rrev_test(self):
        # https://github.com/conan-io/conan/issues/6106
        client = TestClient(revisions_enabled=False)
        client.run("download pkg/1.0@user/channel#fakerevision", assert_error=True)
        self.assertIn(
            "ERROR: Revisions not enabled in the client, specify a reference without revision",
            client.out)

    @unittest.skipUnless(get_env("TESTING_REVISIONS_ENABLED", False), "Only revisions")
    def download_revs_enabled_with_fake_rrev_test(self):
        client = TestClient(default_server_user=True, revisions_enabled=True)
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . pkg/1.0@user/channel")
        client.run("upload * --all --confirm")
        client.run("remove * -f")
        client.run("download pkg/1.0@user/channel#fakerevision", assert_error=True)
        self.assertIn("ERROR: Recipe not found: 'pkg/1.0@user/channel'", client.out)

    @unittest.skipUnless(get_env("TESTING_REVISIONS_ENABLED", False), "Only revisions")
    def download_revs_enabled_with_rrev_test(self):
        ref = ConanFileReference.loads("pkg/1.0@user/channel")
        client = TurboTestClient(default_server_user=True, revisions_enabled=True)
        pref = client.create(ref, conanfile=GenConanfile())
        client.run("upload pkg/1.0@user/channel --all --confirm")
        # create new revision from recipe
        client.create(ref, conanfile=GenConanfile().with_build_msg("new revision"))
        client.run("upload pkg/1.0@user/channel --all --confirm")
        client.run("remove * -f")
        client.run("download pkg/1.0@user/channel#{}".format(pref.ref.revision))
        self.assertIn("pkg/1.0@user/channel: Package installed {}".format(pref.id), client.out)
        search_result = client.search("pkg/1.0@user/channel --revisions")[0]
        self.assertIn(pref.ref.revision, search_result["revision"])

    @unittest.skipUnless(get_env("TESTING_REVISIONS_ENABLED", False), "Only revisions")
    def download_revs_enabled_with_rrev_no_user_channel_test(self):
        ref = ConanFileReference.loads("pkg/1.0@")
        servers = {"default": TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")],
                                         users={"user": "password"})}
        client = TurboTestClient(servers=servers, revisions_enabled=True,
                                 users={"default": [("user", "password")]})
        pref = client.create(ref, conanfile=GenConanfile())
        client.run("upload pkg/1.0@ --all --confirm")
        # create new revision from recipe
        client.create(ref, conanfile=GenConanfile().with_build_msg("new revision"))
        client.run("upload pkg/1.0@ --all --confirm")
        client.run("remove * -f")
        client.run("download pkg/1.0@#{}".format(pref.ref.revision))
        self.assertIn("pkg/1.0: Package installed {}".format(pref.id), client.out)
        search_result = client.search("pkg/1.0@ --revisions")[0]
        self.assertIn(pref.ref.revision, search_result["revision"])

    @unittest.skipUnless(get_env("TESTING_REVISIONS_ENABLED", False), "Only revisions")
    def download_revs_enabled_with_prev_test(self):
        # https://github.com/conan-io/conan/issues/6106
        ref = ConanFileReference.loads("pkg/1.0@user/channel")
        client = TurboTestClient(default_server_user=True, revisions_enabled=True)
        pref = client.create(ref, conanfile=GenConanfile())
        client.run("upload pkg/1.0@user/channel --all --confirm")
        client.create(ref, conanfile=GenConanfile().with_build_msg("new revision"))
        client.run("upload pkg/1.0@user/channel --all --confirm")
        client.run("remove * -f")
        client.run("download pkg/1.0@user/channel#{}:{}#{}".format(pref.ref.revision,
                                                                   pref.id,
                                                                   pref.revision))
        self.assertIn("pkg/1.0@user/channel: Package installed {}".format(pref.id), client.out)
        search_result = client.search("pkg/1.0@user/channel --revisions")[0]
        self.assertIn(pref.ref.revision, search_result["revision"])
        search_result = client.search(
            "pkg/1.0@user/channel#{}:{} --revisions".format(pref.ref.revision, pref.id))[0]
        self.assertIn(pref.revision, search_result["revision"])
