import os
import unittest

import six
from mock import Mock

from conans import DEFAULT_REVISION_V1
from conans.client.userio import UserIO
from conans.model.manifest import FileTreeManifest
from conans.model.ref import PackageReference, ConanFileReference
from conans.paths import PACKAGES_FOLDER, EXPORT_FOLDER, BUILD_FOLDER, SRC_FOLDER, CONANFILE, \
    CONAN_MANIFEST, CONANINFO
from conans.server.store.server_store import ServerStore
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient, TestBufferConanOutput, TestServer, \
    NO_SETTINGS_PACKAGE_ID
from conans.util.files import load


class RemoveRegistryTest(unittest.TestCase):

    def remove_registry_test(self):
        test_server = TestServer(users={"lasote": "password"})  # exported users and passwords
        servers = {"default": test_server}
        client = TestClient(servers=servers, users={"default": [("lasote", "password")]})
        conanfile = """from conans import ConanFile
class Test(ConanFile):
    pass
    """
        client.save({"conanfile.py": conanfile})
        client.run("create . Test/0.1@lasote/testing")
        client.run("upload * --all --confirm")
        client.run('remove "*" -f')
        client.run("remote list_pref Test/0.1@lasote/testing")
        self.assertNotIn("Test/0.1@lasote/testing", client.out)
        registry_content = load(client.client_cache.registry)
        self.assertNotIn("Test/0.1@lasote/testing", registry_content)


class RemoveOutdatedTest(unittest.TestCase):

    def remove_query_test(self):
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

    def remove_outdated_test(self):
        test_server = TestServer(users={"lasote": "password"})  # exported users and passwords
        servers = {"default": test_server}
        client = TestClient(servers=servers, users={"default": [("lasote", "password")]})
        if client.revisions:
            self.skipTest("Makes no sense with revisions")
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
            self.assertIn("os: Windows", client.user_io.out)
            self.assertIn("os: Linux", client.user_io.out)
            client.run("remove Test/0.1@lasote/testing -p --outdated -f %s" % remote)
            client.run("search Test/0.1@lasote/testing  %s" % remote)
            self.assertNotIn("os: Windows", client.user_io.out)
            self.assertIn("os: Linux", client.user_io.out)


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
''' + fake_recipe_hash +  '''
[recipe_revision]
'''


class RemoveTest(unittest.TestCase):

    def setUp(self):
        hello_files = cpp_hello_conan_files("Hello")
        test_conanfile_contents = hello_files[CONANFILE]

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
        pack_refs = []
        for key, folder in self.root_folder.items():
            ref = ConanFileReference.loads(folder)
            folder = folder.replace("@", "/")
            files["%s/%s/conanfile.py" % (folder, EXPORT_FOLDER)] = test_conanfile_contents
            files["%s/%s/conanmanifest.txt" % (folder, EXPORT_FOLDER)] = "%s\nconanfile.py: 234234234" % fake_recipe_hash
            files["%s/%s/conans.txt" % (folder, SRC_FOLDER)] = ""
            for pack_id in (1, 2):
                i = pack_id
                pack_id = "%s_%s" % (pack_id, key)
                pack_refs.append(PackageReference(ref, str(pack_id)))
                files["%s/%s/%s/conans.txt" % (folder, BUILD_FOLDER, pack_id)] = ""
                files["%s/%s/%s/conans.txt" % (folder, PACKAGES_FOLDER, pack_id)] = ""
                files["%s/%s/%s/%s" % (folder, PACKAGES_FOLDER, pack_id, CONANINFO)] = conaninfo % str(i) + "905eefe3570dd09a8453b30b9272bb44"
                files["%s/%s/%s/%s" % (folder, PACKAGES_FOLDER, pack_id, CONAN_MANIFEST)] = ""

            exports_sources_dir = client.client_cache.export_sources(ref)
            os.makedirs(exports_sources_dir)

        client.save(files, client.client_cache.store)

        # Create the manifests to be able to upload
        for pack_ref in pack_refs:
            pkg_folder = client.client_cache.package(pack_ref)
            expected_manifest = FileTreeManifest.create(pkg_folder)
            files["%s/%s/%s/%s" % (pack_ref.conan.dir_repr(),
                                   PACKAGES_FOLDER,
                                   pack_ref.package_id,
                                   CONAN_MANIFEST)] = repr(expected_manifest)

        client.save(files, client.client_cache.store)

        self.client = client

        for folder in self.root_folder.values():
            client.run("upload %s --all" % folder)

        self.assert_folders({"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": True, "H2": True, "B": True, "O": True})

    def assert_folders(self, local_folders, remote_folders, build_folders, src_folders):
        for base_path, folders in [(self.client.paths, local_folders),
                                   (self.server.paths, remote_folders)]:
            root_folder = base_path.store
            for k, shas in folders.items():
                folder = os.path.join(root_folder, self.root_folder[k].replace("@", "/"))
                ref = ConanFileReference.loads(self.root_folder[k])
                if isinstance(base_path, ServerStore):
                    if not self.client.block_v2:
                        try:
                            rev = self.client.get_revision(ref)
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
                            if not self.client.block_v2:
                                pref = PackageReference(ref, sha)
                                try:
                                    prev = self.client.get_package_revision(pref)
                                except:
                                    # This whole test is a crap, we cannot guess remote revision
                                    # if the package is not in local anymore
                                    continue
                            else:
                                prev = DEFAULT_REVISION_V1
                            package_folder += "/%s" % prev
                        if value in shas:
                            self.assertTrue(os.path.exists(package_folder),
                                            "%s doesn't exist " % package_folder)
                        else:
                            self.assertFalse(os.path.exists(package_folder))

        root_folder = self.client.paths.store
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

    def basic_test(self):
        self.client.run("remove hello/* -f")
        self.assert_folders(local_folders={"H1": None, "H2": None, "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": None, "H2": None, "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": False, "H2": False, "B": True, "O": True})
        folders = os.listdir(self.client.storage_folder)
        six.assertCountEqual(self, ["Other", "Bye"], folders)

    def basic_mocked_test(self):
        mocked_user_io = UserIO(out=TestBufferConanOutput())
        mocked_user_io.request_boolean = Mock(return_value=True)
        self.client.run("remove hello/*", user_io=mocked_user_io)
        self.assert_folders(local_folders={"H1": None, "H2": None, "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": None, "H2": None, "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": False, "H2": False, "B": True, "O": True})
        folders = os.listdir(self.client.storage_folder)
        six.assertCountEqual(self, ["Other", "Bye"], folders)

    def basic_packages_test(self):
        self.client.run("remove hello/* -p -f")
        self.assert_folders(local_folders={"H1": [], "H2": [], "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": True, "H2": True, "B": True, "O": True})
        folders = os.listdir(self.client.storage_folder)
        six.assertCountEqual(self, ["Hello", "Other", "Bye"], folders)
        six.assertCountEqual(self, ["build", "source", "export", "export_source", "metadata.json"],
                             os.listdir(os.path.join(self.client.storage_folder,
                                                     "Hello/1.4.10/myuser/testing")))
        six.assertCountEqual(self, ["build", "source", "export", "export_source", "metadata.json"],
                             os.listdir(os.path.join(self.client.storage_folder,
                                                     "Hello/2.4.11/myuser/testing")))

    def builds_test(self):
        mocked_user_io = UserIO(out=TestBufferConanOutput())
        mocked_user_io.request_boolean = Mock(return_value=True)
        self.client.run("remove hello/* -b", user_io=mocked_user_io)
        self.assert_folders(local_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": [], "H2": [], "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": True, "H2": True, "B": True, "O": True})
        folders = os.listdir(self.client.storage_folder)
        six.assertCountEqual(self, ["Hello", "Other", "Bye"], folders)
        six.assertCountEqual(self, ["package", "source", "export", "export_source",
                                    "metadata.json"],
                             os.listdir(os.path.join(self.client.storage_folder,
                                                     "Hello/1.4.10/myuser/testing")))
        six.assertCountEqual(self, ["package", "source", "export", "export_source",
                                    "metadata.json"],
                             os.listdir(os.path.join(self.client.storage_folder,
                                                     "Hello/2.4.11/myuser/testing")))

    def src_test(self):
        mocked_user_io = UserIO(out=TestBufferConanOutput())
        mocked_user_io.request_boolean = Mock(return_value=True)
        self.client.run("remove hello/* -s", user_io=mocked_user_io)
        self.assert_folders(local_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": False, "H2": False, "B": True, "O": True})
        folders = os.listdir(self.client.storage_folder)
        six.assertCountEqual(self, ["Hello", "Other", "Bye"], folders)
        six.assertCountEqual(self, ["package", "build", "export", "export_source", "metadata.json"],
                             os.listdir(os.path.join(self.client.storage_folder,
                                                     "Hello/1.4.10/myuser/testing")))
        six.assertCountEqual(self, ["package", "build", "export", "export_source", "metadata.json"],
                             os.listdir(os.path.join(self.client.storage_folder,
                                                     "Hello/2.4.11/myuser/testing")))

    def reject_removal_test(self):
        mocked_user_io = UserIO(out=TestBufferConanOutput())
        mocked_user_io.request_boolean = Mock(return_value=False)
        self.client.run("remove hello/* -s -b -p", user_io=mocked_user_io)
        self.assert_folders(local_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": True, "H2": True, "B": True, "O": True})

    def remote_build_error_test(self):
        self.client.run("remove hello/* -b -r=default", ignore_error=True)
        self.assertIn("Remotes don't have 'build' or 'src' folder", self.client.user_io.out)
        self.assert_folders(local_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": True, "H2": True, "B": True, "O": True})

    def remote_packages_test(self):
        self.client.run("remove hello/* -p -r=default -f")
        self.assert_folders(local_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [], "H2": [], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": True, "H2": True, "B": True, "O": True})

    def remote_conans_test(self):
        self.client.run("remove hello/* -r=default -f")
        self.assert_folders(local_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": None, "H2": None, "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": True, "H2": True, "B": True, "O": True})
        remote_folder = os.path.join(self.server_folder, ".conan_server/data")
        folders = os.listdir(remote_folder)
        six.assertCountEqual(self, ["Other", "Bye"], folders)

    def remove_specific_package_test(self):
        self.client.run("remove hello/1.4.10* -p=1_H1 -f")
        self.assert_folders(local_folders={"H1": [2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": True, "H2": True, "B": True, "O": True})

    def remove_specific_packages_test(self):
        self.client.run("remove hello/1.4.10* -p=1_H1 -p 2_H1 -f")
        self.assert_folders(local_folders={"H1": [], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": True, "H2": True, "B": True, "O": True})

    def remove_specific_build_test(self):
        self.client.run("remove hello/1.4.10* -b=1_H1 -f")
        self.assert_folders(local_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": [2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": True, "H2": True, "B": True, "O": True})

    def remove_specific_builds_test(self):
        self.client.run("remove hello/1.4.10* -b=1_H1 -b=2_H1 -f")
        self.assert_folders(local_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": [], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": True, "H2": True, "B": True, "O": True})

    def remove_remote_specific_package_test(self):
        self.client.run("remove hello/1.4.10* -p=1_H1 -f -r=default")
        self.assert_folders(local_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": True, "H2": True, "B": True, "O": True})

    def remove_remote_specific_packages_test(self):
        self.client.run("remove hello/1.4.10* -p=1_H1 -p2_H1 -f -r=default")
        self.assert_folders(local_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": True, "H2": True, "B": True, "O": True})

    def try_remove_using_query_and_packages_or_builds_test(self):
        with self.assertRaisesRegexp(Exception, "Command failed"):
            self.client.run("remove hello/1.4.10@lasote/stable -p=1_H1 -q 'compiler.version=4.8' ")
            self.assertIn("'-q' and '-p' parameters can't be used at the same time", self.client.out)

        with self.assertRaisesRegexp(Exception, "Command failed"):
            self.client.run("remove hello/1.4.10@lasote/stable -b=1_H1 -q 'compiler.version=4.8' ")
            self.assertIn("'-q' and '-b' parameters can't be used at the same time", self.client.out)

    def query_remove_locally_test(self):
        self.client.run("remove hello/1.4.10@myuser/testing -q='compiler.version=4.4' -f")
        self.assertIn("No matching packages to remove", self.client.user_io.out)
        self.assert_folders({"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": True, "H2": True, "B": True, "O": True})

        self.client.run('remove Hello/1.4.10@myuser/testing -q="compiler.version=8.1" -f')
        self.assertNotIn("No packages matching the query", self.client.user_io.out)
        self.assert_folders(local_folders={"H1": [2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": True, "H2": True, "B": True, "O": True})

        self.client.run('remove Hello/1.4.10@myuser/testing -q="compiler.version=8.2" -f')
        self.assertNotIn("No packages matching the query", self.client.user_io.out)
        self.assert_folders(local_folders={"H1": [], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": True, "H2": True, "B": True, "O": True})

        self.client.run('remove Hello/1.4.10@myuser/testing -q="compiler.version=8.2" -f -r default')
        self.assertNotIn("No packages matching the query", self.client.user_io.out)
        self.assert_folders(local_folders={"H1": [], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            remote_folders={"H1": [1], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            build_folders={"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            src_folders={"H1": True, "H2": True, "B": True, "O": True})
