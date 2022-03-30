import os
import sys
import unittest

import six
from mock import patch
import pytest

from conans import DEFAULT_REVISION_V1
from conans.model.manifest import FileTreeManifest
from conans.model.package_metadata import PackageMetadata
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import BUILD_FOLDER, CONANINFO, CONAN_MANIFEST, EXPORT_FOLDER, \
    PACKAGES_FOLDER, SRC_FOLDER
from conans.server.store.server_store import ServerStore
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, TestServer, GenConanfile
from conans.util.env_reader import get_env
from conans.util.files import load


class RemoveLocksTest(unittest.TestCase):
    def test_remove_locks(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_name("Hello").with_version("0.1")})
        client.run("create . lasote/testing")
        self.assertNotIn('does not contain a number!', client.out)
        ref = ConanFileReference.loads("Hello/0.1@lasote/testing")
        conan_folder = client.cache.package_layout(ref).base_folder()
        self.assertIn("locks", os.listdir(conan_folder))
        self.assertTrue(os.path.exists(conan_folder + ".count"))
        self.assertTrue(os.path.exists(conan_folder + ".count.lock"))
        client.run("remove * --locks", assert_error=True)
        self.assertIn("ERROR: Specifying a pattern is not supported", client.out)
        client.run("remove", assert_error=True)
        self.assertIn('ERROR: Please specify a pattern to be removed ("*" for all)', client.out)
        client.run("remove --locks")
        self.assertNotIn("locks", os.listdir(conan_folder))
        self.assertFalse(os.path.exists(conan_folder + ".count"))
        self.assertFalse(os.path.exists(conan_folder + ".count.lock"))


class RemoveRegistryTest(unittest.TestCase):

    def test_remove_registry(self):
        test_server = TestServer(users={"lasote": "password"})  # exported users and passwords
        servers = {"default": test_server}
        client = TestClient(servers=servers, users={"default": [("lasote", "password")]})
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . Test/0.1@lasote/testing")
        client.run("upload * --all --confirm")
        client.run('remove "*" -f')
        client.run("remote list_pref Test/0.1@lasote/testing")
        self.assertNotIn("Test/0.1@lasote/testing", client.out)
        registry_content = load(client.cache.remotes_path)
        self.assertNotIn("Test/0.1@lasote/testing", registry_content)


class RemoveOutdatedTest(unittest.TestCase):

    def test_remove_query(self):
        test_server = TestServer(users={"lasote": "password"})  # exported users and passwords
        servers = {"default": test_server}
        client = TestClient(servers=servers, users={"default": [("lasote", "password")]})
        conanfile = """from conans import ConanFile
class Test(ConanFile):
    settings = "os"
    """
        client.save({"conanfile.py": conanfile})
        client.run("create . Test/0.1@lasote/testing -s os=Windows")
        client.run("create . Test/0.1@lasote/testing -s os=Linux")
        client.save({"conanfile.py": conanfile.replace("settings", "pass #")})
        client.run("create . Test2/0.1@lasote/testing")
        client.run("upload * --all --confirm")
        for remote in ("", "-r=default"):
            client.run("remove Test/0.1@lasote/testing -q=os=Windows -f %s" % remote)
            client.run("search Test/0.1@lasote/testing %s" % remote)
            self.assertNotIn("os: Windows", client.out)
            self.assertIn("os: Linux", client.out)

            client.run("remove Test2/0.1@lasote/testing -q=os=Windows -f %s" % remote)
            client.run("search Test2/0.1@lasote/testing %s" % remote)
            self.assertIn("Package_ID: %s" % NO_SETTINGS_PACKAGE_ID, client.out)
            client.run("remove Test2/0.1@lasote/testing -q=os=None -f %s" % remote)
            client.run("search Test2/0.1@lasote/testing %s" % remote)
            self.assertNotIn("Package_ID: %s" % NO_SETTINGS_PACKAGE_ID, client.out)
            self.assertIn("There are no packages", client.out)

    @pytest.mark.skipif(get_env("TESTING_REVISIONS_ENABLED", False), reason="No sense with revs")
    def test_remove_outdated(self):
        test_server = TestServer(users={"lasote": "password"})  # exported users and passwords
        servers = {"default": test_server}
        client = TestClient(servers=servers, users={"default": [("lasote", "password")]})
        conanfile = """from conans import ConanFile
class Test(ConanFile):
    name = "Test"
    version = "0.1"
    settings = "os"
    """
        client.save({"conanfile.py": conanfile})
        client.run("export . lasote/testing")
        client.run("install Test/0.1@lasote/testing --build -s os=Windows")
        client.save({"conanfile.py": "# comment\n%s" % conanfile})
        client.run("export . lasote/testing")
        client.run("install Test/0.1@lasote/testing --build -s os=Linux")
        client.run("upload * --all --confirm")
        for remote in ("", "-r=default"):
            client.run("search Test/0.1@lasote/testing %s" % remote)
            self.assertIn("os: Windows", client.out)
            self.assertIn("os: Linux", client.out)
            client.run("remove Test/0.1@lasote/testing -p --outdated -f %s" % remote)
            client.run("search Test/0.1@lasote/testing  %s" % remote)
            self.assertNotIn("os: Windows", client.out)
            self.assertIn("os: Linux", client.out)


fake_recipe_hash = "999999999"
conaninfo = '''
[settings]
    arch=x64
    os=Windows
    compiler=Visual Studio
    compiler.version=8.%s
[options]
    use_Qt=True
[full_requires]
  Hello2/0.1@lasote/stable:11111
  OpenSSL/2.10@lasote/testing:2222
  HelloInfo1/0.45@myuser/testing:33333
[recipe_hash]
''' + fake_recipe_hash + '''
[recipe_revision]
'''


class RemoveTest(unittest.TestCase):

    def setUp(self):
        test_conanfile_contents = str(GenConanfile("Hello", "0.1"))
        hello_files = {"conanfile.py": test_conanfile_contents}

        self.server_folder = temp_folder()
        test_server = TestServer(users={"myuser": "mypass"},
                                 base_path=self.server_folder)  # exported users and passwords
        self.server = test_server
        servers = {"default": test_server}
        client = TestClient(servers=servers, users={"default": [("myuser", "mypass")]})

        # Conans with and without packages created
        self.root_folder = {"H1": 'Hello/1.4.10@myuser/testing',
                            "H2": 'Hello/2.4.11@myuser/testing',
                            "B": 'Bye/0.14@myuser/testing',
                            "O": 'Other/1.2@myuser/testing'}

        files = {}
        prefs = []
        for key, folder in self.root_folder.items():
            ref = ConanFileReference.loads(folder)
            folder = folder.replace("@", "/")
            fake_metadata = PackageMetadata()
            fake_metadata.recipe.revision = DEFAULT_REVISION_V1
            files["%s/%s/conanfile.py" % (folder, EXPORT_FOLDER)] = test_conanfile_contents
            files["%s/%s/conanmanifest.txt" % (
                folder, EXPORT_FOLDER)] = "%s\nconanfile.py: 234234234" % fake_recipe_hash
            files["%s/%s/conans.txt" % (folder, SRC_FOLDER)] = ""
            for pack_id in (1, 2):
                i = pack_id
                pack_id = "%s_%s" % (pack_id, key)
                fake_metadata.packages[pack_id].revision = DEFAULT_REVISION_V1
                prefs.append(PackageReference(ref, str(pack_id)))
                files["%s/%s/%s/conans.txt" % (folder, BUILD_FOLDER, pack_id)] = ""
                files["%s/%s/%s/conans.txt" % (folder, PACKAGES_FOLDER, pack_id)] = ""
                files[
                    "%s/%s/%s/%s" % (folder, PACKAGES_FOLDER, pack_id, CONANINFO)] = conaninfo % str(
                    i) + "905eefe3570dd09a8453b30b9272bb44"
                files["%s/%s/%s/%s" % (folder, PACKAGES_FOLDER, pack_id, CONAN_MANIFEST)] = ""
            files["%s/metadata.json" % folder] = fake_metadata.dumps()
            exports_sources_dir = client.cache.package_layout(ref).export_sources()
            os.makedirs(exports_sources_dir)

        client.save(files, client.cache.store)

        # Create the manifests to be able to upload
        for pref in prefs:
            pkg_folder = client.cache.package_layout(pref.ref).package(pref)
            expected_manifest = FileTreeManifest.create(pkg_folder)
            files["%s/%s/%s/%s" % (pref.ref.dir_repr(),
                                   PACKAGES_FOLDER,
                                   pref.id,
                                   CONAN_MANIFEST)] = repr(expected_manifest)

        client.save(files, client.cache.store)

        self.client = client

        for folder in self.root_folder.values():
            client.run("upload %s --all" % folder)

        self.assert_folders({"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": True, "H2": True, "B": True, "O": True})

    def assert_folders(self, local_folders, remote_folders, build_folders, src_folders):
        for base_path, folders in [(self.client.cache, local_folders),
                                   (self.server.server_store, remote_folders)]:
            root_folder = base_path.store
            for k, shas in folders.items():
                folder = os.path.join(root_folder, self.root_folder[k].replace("@", "/"))
                ref = ConanFileReference.loads(self.root_folder[k])
                if isinstance(base_path, ServerStore):
                    if self.client.cache.config.revisions_enabled:
                        try:
                            rev = self.client.cache.package_layout(ref).recipe_revision()
                        except:
                            # This whole test is a crap, we cannot guess remote revision
                            # if the package is not in local anymore
                            continue
                    else:
                        rev = DEFAULT_REVISION_V1
                    folder += "/%s" % rev
                if shas is None:
                    self.assertFalse(os.path.exists(folder))
                else:
                    for value in (1, 2):
                        sha = "%s_%s" % (value, k)
                        package_folder = os.path.join(folder, "package", sha)
                        if isinstance(base_path, ServerStore):
                            if self.client.cache.config.revisions_enabled:
                                pref = PackageReference(ref, sha)
                                try:
                                    layout = self.client.cache.package_layout(pref.ref)
                                    prev = layout.package_revision(pref)
                                except:
                                    # This whole test is a crap, we cannot guess remote revision
                                    # if the package is not in local anymore
                                    continue
                            else:
                                prev = DEFAULT_REVISION_V1
                            package_folder += "/%s" % prev if prev else ""
                        if value in shas:
                            self.assertTrue(os.path.exists(package_folder),
                                            "%s doesn't exist " % package_folder)
                        else:
                            self.assertFalse(os.path.exists(package_folder), package_folder)

        root_folder = self.client.cache.store
        for k, shas in build_folders.items():
            folder = os.path.join(root_folder, self.root_folder[k].replace("@", "/"))
            if shas is None:
                self.assertFalse(os.path.exists(folder))
            else:
                for value in (1, 2):
                    sha = "%s_%s" % (value, k)
                    build_folder = os.path.join(folder, "build", sha)
                    if value in shas:
                        self.assertTrue(os.path.exists(build_folder))
                    else:
                        self.assertFalse(os.path.exists(build_folder))
        for k, value in src_folders.items():
            folder = os.path.join(root_folder, self.root_folder[k].replace("@", "/"), "source")
            if value:
                self.assertTrue(os.path.exists(folder))
            else:
                self.assertFalse(os.path.exists(folder))

    def test_basic(self):
        self.client.run("remove hello/* -f")
        self.assert_folders(local_folders={"H1": None, "H2": None, "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": None, "H2": None, "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": False, "H2": False, "B": True, "O": True})
        folders = os.listdir(self.client.storage_folder)
        six.assertCountEqual(self, ["Other", "Bye"], folders)

    def test_basic_mocked(self):
        with patch.object(sys.stdin, "readline", return_value="y"):
            self.client.run("remove hello/*")
        self.assert_folders(local_folders={"H1": None, "H2": None, "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": None, "H2": None, "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": False, "H2": False, "B": True, "O": True})
        folders = os.listdir(self.client.storage_folder)
        six.assertCountEqual(self, ["Other", "Bye"], folders)

    def test_basic_packages(self):
        self.client.run("remove hello/* -p -f")
        self.assert_folders(local_folders={"H1": [], "H2": [], "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": True, "H2": True, "B": True, "O": True})
        folders = os.listdir(self.client.storage_folder)
        six.assertCountEqual(self, ["Hello", "Other", "Bye"], folders)
        six.assertCountEqual(self, ["build", "source", "export", "export_source", "metadata.json",
                                    "dl", "metadata.json.lock"],
                             os.listdir(os.path.join(self.client.storage_folder,
                                                     "Hello/1.4.10/myuser/testing")))
        six.assertCountEqual(self, ["build", "source", "export", "export_source", "metadata.json",
                                    "dl", "metadata.json.lock"],
                             os.listdir(os.path.join(self.client.storage_folder,
                                                     "Hello/2.4.11/myuser/testing")))

    def _validate_remove_all_hello_packages(self):
        self.assert_folders(local_folders={"H1": None, "H2": None, "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": None, "H2": None, "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": False, "H2": False, "B": True, "O": True})
        folders = os.listdir(self.client.storage_folder)
        six.assertCountEqual(self, ["Other", "Bye"], folders)

    def test_remove_any_package_version(self):
        self.client.run("remove Hello/*@myuser/testing -f")
        self._validate_remove_all_hello_packages()

    def test_remove_any_package_version_user(self):
        self.client.run("remove Hello/*@*/testing -f")
        self._validate_remove_all_hello_packages()

    def test_remove_any_package_version_channel(self):
        self.client.run("remove Hello/*@*/* -f")
        self._validate_remove_all_hello_packages()

    def _validate_remove_hello_1_4_10(self):
        self.assert_folders(local_folders={"H1": None, "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": None, "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": False, "H2": True, "B": True, "O": True})
        folders = os.listdir(self.client.storage_folder)
        six.assertCountEqual(self, ["Hello", "Other", "Bye"], folders)

    def test_remove_any_package_user(self):
        self.client.run("remove Hello/1.4.10@*/testing -f")
        self._validate_remove_hello_1_4_10()

    def test_remove_any_package_channel(self):
        self.client.run("remove Hello/1.4.10@myuser/* -f")
        self._validate_remove_hello_1_4_10()

    def test_builds(self):
        with patch.object(sys.stdin, "readline", return_value="y"):
            self.client.run("remove hello/* -b")
        self.assert_folders(local_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": [], "H2": [], "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": True, "H2": True, "B": True, "O": True})
        folders = os.listdir(self.client.storage_folder)
        six.assertCountEqual(self, ["Hello", "Other", "Bye"], folders)
        six.assertCountEqual(self, ["package", "dl", "source", "export", "export_source",
                                    "metadata.json", "metadata.json.lock"],
                             os.listdir(os.path.join(self.client.storage_folder,
                                                     "Hello/1.4.10/myuser/testing")))
        six.assertCountEqual(self, ["package", "dl", "source", "export", "export_source",
                                    "metadata.json", "metadata.json.lock"],
                             os.listdir(os.path.join(self.client.storage_folder,
                                                     "Hello/2.4.11/myuser/testing")))

    def test_src(self):
        with patch.object(sys.stdin, "readline", return_value="y"):
            self.client.run("remove hello/* -s")
        self.assert_folders(local_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": False, "H2": False, "B": True, "O": True})
        folders = os.listdir(self.client.storage_folder)
        six.assertCountEqual(self, ["Hello", "Other", "Bye"], folders)
        six.assertCountEqual(self, ["package", "build", "export", "export_source", "metadata.json",
                                    "dl", "metadata.json.lock"],
                             os.listdir(os.path.join(self.client.storage_folder,
                                                     "Hello/1.4.10/myuser/testing")))
        six.assertCountEqual(self, ["package", "build", "export", "export_source", "metadata.json",
                                    "dl", "metadata.json.lock"],
                             os.listdir(os.path.join(self.client.storage_folder,
                                                     "Hello/2.4.11/myuser/testing")))

    def test_reject_removal(self):
        with patch.object(sys.stdin, "readline", return_value="n"):
            self.client.run("remove hello/* -s -b -p")
        self.assert_folders(local_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": True, "H2": True, "B": True, "O": True})

    def test_remote_build_error(self):
        self.client.run("remove hello/* -b -r=default", assert_error=True)
        self.assertIn("Remotes don't have 'build' or 'src' folder", self.client.out)
        self.assert_folders(local_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": True, "H2": True, "B": True, "O": True})

    def test_remote_packages(self):
        self.client.run("remove hello/* -p -r=default -f")
        self.assert_folders(local_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [], "H2": [], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": True, "H2": True, "B": True, "O": True})

    def test_remote_conans(self):
        self.client.run("remove hello/* -r=default -f")
        self.assert_folders(local_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": None, "H2": None, "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": True, "H2": True, "B": True, "O": True})
        remote_folder = os.path.join(self.server_folder, ".conan_server/data")
        folders = os.listdir(remote_folder)
        six.assertCountEqual(self, ["Other", "Bye"], folders)

    def test_remove_specific_package(self):
        self.client.run("remove hello/1.4.10* -p=1_H1 -f")
        self.assert_folders(local_folders={"H1": [2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": True, "H2": True, "B": True, "O": True})

    def test_remove_specific_packages(self):
        self.client.run("remove hello/1.4.10* -p=1_H1 -p 2_H1 -f")
        self.assert_folders(local_folders={"H1": [], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": True, "H2": True, "B": True, "O": True})

    def test_remove_specific_build(self):
        self.client.run("remove hello/1.4.10* -b=1_H1 -f")
        self.assert_folders(local_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": [2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": True, "H2": True, "B": True, "O": True})

    def test_remove_specific_builds(self):
        self.client.run("remove hello/1.4.10* -b=1_H1 -b=2_H1 -f")
        self.assert_folders(local_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": [], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": True, "H2": True, "B": True, "O": True})

    def test_remove_remote_specific_package(self):
        self.client.run("remove hello/1.4.10* -p=1_H1 -f -r=default")
        self.assert_folders(local_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": True, "H2": True, "B": True, "O": True})

    def test_remove_remote_specific_packages(self):
        self.client.run("remove hello/1.4.10* -p=1_H1 -p2_H1 -f -r=default")
        self.assert_folders(local_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": True, "H2": True, "B": True, "O": True})

    def test_try_remove_using_query_and_packages_or_builds(self):
        with six.assertRaisesRegex(self, Exception, "Command failed"):
            self.client.run("remove hello/1.4.10@lasote/stable -p=1_H1 -q 'compiler.version=4.8' ")
            self.assertIn("'-q' and '-p' parameters can't be used at the same time", self.client.out)

        with six.assertRaisesRegex(self, Exception, "Command failed"):
            self.client.run("remove hello/1.4.10@lasote/stable -b=1_H1 -q 'compiler.version=4.8' ")
            self.assertIn("'-q' and '-b' parameters can't be used at the same time", self.client.out)

    @pytest.mark.skipif(get_env("TESTING_REVISIONS_ENABLED", False), reason="This test is insane to be "
                                                                            "tested with revisions, in "
                                                                            "general all the module")
    def test_query_remove_locally(self):
        self.client.run("remove notfoundname/1.4.10@myuser/testing -q='compiler.version=4.4' -f",
                        assert_error=True)
        self.assertIn("Recipe not found: 'notfoundname/1.4.10@myuser/testing'", self.client.out)
        self.assert_folders({"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": True, "H2": True, "B": True, "O": True})

        self.client.run('remove Hello/1.4.10@myuser/testing -q="compiler.version=8.1" -f')
        self.assertNotIn("No packages matching the query", self.client.out)
        self.assert_folders(local_folders={"H1": [2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": True, "H2": True, "B": True, "O": True})

        self.client.run('remove Hello/1.4.10@myuser/testing -q="compiler.version=8.2" -f')
        self.assertNotIn("No packages matching the query", self.client.out)
        self.assert_folders(local_folders={"H1": [], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": True, "H2": True, "B": True, "O": True})

        self.client.run('remove Hello/1.4.10@myuser/testing -q="compiler.version=8.2" -f -r default')
        self.assertNotIn("No packages matching the query", self.client.out)
        self.assert_folders(local_folders={"H1": [], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [1], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": True, "H2": True, "B": True, "O": True})


class RemoveWithoutUserChannel(unittest.TestCase):

    def setUp(self):
        self.test_server = TestServer(users={"lasote": "password"},
                                      write_permissions=[("lib/1.0@*/*", "lasote")])
        servers = {"default": self.test_server}
        self.client = TestClient(servers=servers, users={"default": [("lasote", "password")]})

    def test_local(self):
        self.client.save({"conanfile.py": GenConanfile()})
        self.client.run("create . lib/1.0@")
        self.client.run("remove lib/1.0 -f")
        folder = self.client.cache.package_layout(ConanFileReference.loads("lib/1.0@")).export()
        self.assertFalse(os.path.exists(folder))

    def test_remote(self):
        self.client.save({"conanfile.py": GenConanfile()})
        self.client.run("create . lib/1.0@")
        self.client.run("upload lib/1.0 -r default -c --all")
        self.client.run("remove lib/1.0 -f")
        # we can still install it
        self.client.run("install lib/1.0@")
        self.assertIn("Installing package: lib/1.0", self.client.out)
        self.client.run("remove lib/1.0 -f")

        # Now remove remotely
        self.client.run("remove lib/1.0 -f -r default")
        self.client.run("install lib/1.0@", assert_error=True)
        self.assertIn("ERROR: Unable to find 'lib/1.0' in remotes", self.client.out)


class RemovePackageRevisionsTest(unittest.TestCase):

    NO_SETTINGS_RREF = "f3367e0e7d170aa12abccb175fee5f97"

    def setUp(self):
        self.test_server = TestServer(users={"user": "password"},
                                      write_permissions=[("foobar/0.1@*/*", "user")])
        servers = {"default": self.test_server}
        self.client = TestClient(servers=servers, users={"default": [("user", "password")]})
        self.client.run("config set general.revisions_enabled=1")

    def test_remove_local_package_id_argument(self):
        """ Remove package ID based on recipe revision. The package must be deleted, but
            the recipe must be preserved
            Package ID is a separated argument: <package>#<rref> -p <pkgid>
        """
        self.client.save({"conanfile.py": GenConanfile()})
        self.client.run("create . foobar/0.1@user/testing")
        self.client.run("info foobar/0.1@user/testing")
        self.assertIn("Binary: Cache", self.client.out)
        self.assertIn("Revision: f3367e0e7d170aa12abccb175fee5f97", self.client.out)
        self.assertIn("Package revision: 83c38d3b4e5f1b8450434436eec31b00", self.client.out)

        self.client.run("remove -f foobar/0.1@user/testing#{} -p {}"
                        .format(self.NO_SETTINGS_RREF, NO_SETTINGS_PACKAGE_ID))
        self.client.run("info foobar/0.1@user/testing")
        self.assertIn("Binary: Missing", self.client.out)
        self.assertIn("Revision: f3367e0e7d170aa12abccb175fee5f97", self.client.out)
        self.assertIn("Package revision: None", self.client.out)

    def test_remove_local_package_id_reference(self):
        """ Remove package ID based on recipe revision. The package must be deleted, but
            the recipe must be preserved.
            Package ID is part of package reference: <package>#<rref>:<pkgid>
        """
        self.client.save({"conanfile.py": GenConanfile()})
        self.client.run("create . foobar/0.1@user/testing")
        self.client.run("info foobar/0.1@user/testing")
        self.assertIn("Binary: Cache", self.client.out)
        self.assertIn("Revision: f3367e0e7d170aa12abccb175fee5f97", self.client.out)
        self.assertIn("Package revision: 83c38d3b4e5f1b8450434436eec31b00", self.client.out)

        self.client.run("remove -f foobar/0.1@user/testing#{}:{}"
                        .format(self.NO_SETTINGS_RREF, NO_SETTINGS_PACKAGE_ID))
        self.client.run("info foobar/0.1@user/testing")
        self.assertIn("Binary: Missing", self.client.out)
        self.assertIn("Revision: f3367e0e7d170aa12abccb175fee5f97", self.client.out)
        self.assertIn("Package revision: None", self.client.out)

    def test_remove_duplicated_package_id(self):
        """ The package ID must not be present in both -p argument and package reference
        """
        self.client.save({"conanfile.py": GenConanfile()})
        self.client.run("create . foobar/0.1@user/testing")
        self.client.run("remove -f foobar/0.1@user/testing#{}:{} -p {}"
                        .format(self.NO_SETTINGS_RREF, NO_SETTINGS_PACKAGE_ID,
                                NO_SETTINGS_PACKAGE_ID), assert_error=True)
        self.assertIn("Use package ID only as -p argument or reference, not both", self.client.out)

    def test_remove_remote_package_id_reference(self):
        """ Remove remote package ID based on recipe revision. The package must be deleted, but
            the recipe must be preserved.
            Package ID is part of package reference: <package>#<rref>:<pkgid>
        """
        self.client.save({"conanfile.py": GenConanfile()})
        self.client.run("create . foobar/0.1@user/testing")
        self.client.run("upload foobar/0.1@user/testing -r default -c --all")
        self.client.run("remove -f foobar/0.1@user/testing#{}:{}"
                        .format(self.NO_SETTINGS_RREF, NO_SETTINGS_PACKAGE_ID))
        self.client.run("info foobar/0.1@user/testing")
        self.assertIn("Binary: Download", self.client.out)
        self.client.run("remove -f foobar/0.1@user/testing#{}:{} -r default"
                        .format(self.NO_SETTINGS_RREF, NO_SETTINGS_PACKAGE_ID))
        self.client.run("info foobar/0.1@user/testing")
        self.assertIn("Binary: Missing", self.client.out)
