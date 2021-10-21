import os
import sys
import unittest

import pytest
from mock import patch

from conans.model.manifest import FileTreeManifest
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import BUILD_FOLDER, CONANINFO, CONAN_MANIFEST, EXPORT_FOLDER, \
    PACKAGES_FOLDER, SRC_FOLDER
from conans.server.store.server_store import ServerStore
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, TestServer, GenConanfile
from conans.util.files import load


@pytest.mark.xfail(reason="cache2.0: TODO: FIX for new locking system")
class RemoveLocksTest(unittest.TestCase):
    def test_remove_locks(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_name("Hello").with_version("0.1")})
        client.run("create . lasote/testing")
        self.assertNotIn('does not contain a number!', client.out)
        ref = ConanFileReference.loads("Hello/0.1@lasote/testing")
        conan_folder = client.get_latest_ref_layout(ref).base_folder()
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


class RemoveOutdatedTest(unittest.TestCase):

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_remove_query(self):
        test_server = TestServer(users={"admin": "password"})  # exported users and passwords
        servers = {"default": test_server}
        client = TestClient(servers=servers, inputs=["admin", "password"])
        conanfile = """from conans import ConanFile
class Test(ConanFile):
    settings = "os"
    """
        client.save({"conanfile.py": conanfile})
        client.run("create . Test/0.1@lasote/testing -s os=Windows")
        client.run("create . Test/0.1@lasote/testing -s os=Linux")
        client.save({"conanfile.py": conanfile.replace("settings", "pass #")})
        client.run("create . Test2/0.1@lasote/testing")
        client.run("upload * --all --confirm -r default")
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
[recipe_revision]
'''


@pytest.mark.xfail(reason="cache2.0: TODO: Write new tests for 2.0")
class RemoveTest(unittest.TestCase):

    def setUp(self):
        test_conanfile_contents = str(GenConanfile("Hello", "0.1"))
        hello_files = {"conanfile.py": test_conanfile_contents}

        self.server_folder = temp_folder()
        test_server = TestServer(users={"myuser": "mypass"},
                                 base_path=self.server_folder)  # exported users and passwords
        self.server = test_server
        servers = {"default": test_server}
        client = TestClient(servers=servers, inputs=["myuser", "mypass"])

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
            files["%s/%s/conanfile.py" % (folder, EXPORT_FOLDER)] = test_conanfile_contents
            files["%s/%s/conanmanifest.txt" % (folder, EXPORT_FOLDER)] = \
                "123\nconanfile.py: 234234234"
            files["%s/%s/conans.txt" % (folder, SRC_FOLDER)] = ""
            for pack_id in (1, 2):
                i = pack_id
                pack_id = "%s_%s" % (pack_id, key)
                prefs.append(PackageReference(ref, str(pack_id)))
                files["%s/%s/%s/conans.txt" % (folder, BUILD_FOLDER, pack_id)] = ""
                files["%s/%s/%s/conans.txt" % (folder, PACKAGES_FOLDER, pack_id)] = ""
                files[
                    "%s/%s/%s/%s" % (folder, PACKAGES_FOLDER, pack_id, CONANINFO)] = conaninfo % str(
                    i) + "905eefe3570dd09a8453b30b9272bb44"
                files["%s/%s/%s/%s" % (folder, PACKAGES_FOLDER, pack_id, CONAN_MANIFEST)] = ""
            exports_sources_dir = client.get_latest_ref_layout(ref).export_sources()
            os.makedirs(exports_sources_dir)

        client.save(files, client.cache.store)

        # Create the manifests to be able to upload
        for pref in prefs:
            pkg_folder = client.get_latest_pkg_layout(pref).package()
            expected_manifest = FileTreeManifest.create(pkg_folder)
            files["%s/%s/%s/%s" % (pref.ref.dir_repr(),
                                   PACKAGES_FOLDER,
                                   pref.id,
                                   CONAN_MANIFEST)] = repr(expected_manifest)

        client.save(files, client.cache.store)

        self.client = client

        for folder in self.root_folder.values():
            client.run("upload %s --all -r default" % folder)

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
                    try:
                        rev = self.client.cache.get_latest_rrev(ref).revision
                    except:
                        # This whole test is a crap, we cannot guess remote revision
                        # if the package is not in local anymore
                        continue
                    folder += "/%s" % rev
                if shas is None:
                    self.assertFalse(os.path.exists(folder))
                else:
                    for value in (1, 2):
                        sha = "%s_%s" % (value, k)
                        package_folder = os.path.join(folder, "package", sha)
                        if isinstance(base_path, ServerStore):
                            pref = PackageReference(ref, sha)
                            try:
                                prev = self.client.cache.get_latest_prev(pref).revision
                            except:
                                # This whole test is a crap, we cannot guess remote revision
                                # if the package is not in local anymore
                                continue
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
        self.assertCountEqual(["Other", "Bye"], folders)

    def test_basic_mocked(self):
        with patch.object(sys.stdin, "readline", return_value="y"):
            self.client.run("remove hello/*")
        self.assert_folders(local_folders={"H1": None, "H2": None, "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": None, "H2": None, "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": False, "H2": False, "B": True, "O": True})
        folders = os.listdir(self.client.storage_folder)
        self.assertCountEqual(["Other", "Bye"], folders)

    def test_basic_packages(self):
        self.client.run("remove hello/* -p -f")
        self.assert_folders(local_folders={"H1": [], "H2": [], "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": True, "H2": True, "B": True, "O": True})
        folders = os.listdir(self.client.storage_folder)
        self.assertCountEqual(["Hello", "Other", "Bye"], folders)
        self.assertCountEqual(["build", "source", "export", "export_source", "metadata.json",
                                    "dl", "metadata.json.lock"],
                             os.listdir(os.path.join(self.client.storage_folder,
                                                     "Hello/1.4.10/myuser/testing")))
        self.assertCountEqual(["build", "source", "export", "export_source", "metadata.json",
                                    "dl", "metadata.json.lock"],
                             os.listdir(os.path.join(self.client.storage_folder,
                                                     "Hello/2.4.11/myuser/testing")))

    def _validate_remove_all_hello_packages(self):
        self.assert_folders(local_folders={"H1": None, "H2": None, "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": None, "H2": None, "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": False, "H2": False, "B": True, "O": True})
        folders = os.listdir(self.client.storage_folder)
        self.assertCountEqual(["Other", "Bye"], folders)

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
        self.assertCountEqual(["Hello", "Other", "Bye"], folders)

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
        self.assertCountEqual(["Hello", "Other", "Bye"], folders)
        self.assertCountEqual(["package", "dl", "source", "export", "export_source",
                                    "metadata.json", "metadata.json.lock"],
                             os.listdir(os.path.join(self.client.storage_folder,
                                                     "Hello/1.4.10/myuser/testing")))
        self.assertCountEqual(["package", "dl", "source", "export", "export_source",
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
        self.assertCountEqual(["Hello", "Other", "Bye"], folders)
        self.assertCountEqual(["package", "build", "export", "export_source", "metadata.json",
                                    "dl", "metadata.json.lock"],
                             os.listdir(os.path.join(self.client.storage_folder,
                                                     "Hello/1.4.10/myuser/testing")))
        self.assertCountEqual(["package", "build", "export", "export_source", "metadata.json",
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
        self.assertCountEqual(["Other", "Bye"], folders)

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
        with self.assertRaisesRegex(Exception, "Command failed"):
            self.client.run("remove hello/1.4.10@lasote/stable -p=1_H1 -q 'compiler.version=4.8' ")
            self.assertIn("'-q' and '-p' parameters can't be used at the same time", self.client.out)

        with self.assertRaisesRegex(Exception, "Command failed"):
            self.client.run("remove hello/1.4.10@lasote/stable -b=1_H1 -q 'compiler.version=4.8' ")
            self.assertIn("'-q' and '-b' parameters can't be used at the same time", self.client.out)


class RemoveWithoutUserChannel(unittest.TestCase):

    def setUp(self):
        self.test_server = TestServer(users={"lasote": "password"},
                                      write_permissions=[("lib/1.0@*/*", "lasote")])
        servers = {"default": self.test_server}
        self.client = TestClient(servers=servers, inputs=["lasote", "password"])

    def test_local(self):
        self.client.save({"conanfile.py": GenConanfile()})
        self.client.run("create . lib/1.0@")
        latest_rrev = self.client.cache.get_latest_rrev(ConanFileReference.loads("lib/1.0"))
        ref_layout = self.client.cache.ref_layout(latest_rrev)
        pkg_ids = self.client.cache.get_package_ids(latest_rrev)
        latest_prev = self.client.cache.get_latest_prev(pkg_ids[0])
        pkg_layout = self.client.cache.pkg_layout(latest_prev)
        self.client.run("remove lib/1.0 -f")
        self.assertFalse(os.path.exists(ref_layout.base_folder))
        self.assertFalse(os.path.exists(pkg_layout.base_folder))

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

        self.assertIn("Unable to find 'lib/1.0' in remotes", self.client.out)


class RemovePackageRevisionsTest(unittest.TestCase):

    NO_SETTINGS_RREF = "f3367e0e7d170aa12abccb175fee5f97"

    def setUp(self):
        self.test_server = TestServer(users={"user": "password"},
                                      write_permissions=[("foobar/0.1@*/*", "user")])
        servers = {"default": self.test_server}
        self.client = TestClient(servers=servers, inputs=["user", "password"])

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
        self.assertIn("Package revision: cf924fbb5ed463b8bb960cf3a4ad4f3a", self.client.out)

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
        self.assertIn("Package revision: cf924fbb5ed463b8bb960cf3a4ad4f3a", self.client.out)

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
