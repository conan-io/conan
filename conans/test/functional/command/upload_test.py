import itertools
import os
import platform
import stat
import unittest
from collections import OrderedDict

from mock import mock, patch
from nose.plugins.attrib import attr

from conans.client.cmd.uploader import CmdUpload
from conans.client.tools.env import environment_append
from conans.errors import ConanException
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import EXPORT_SOURCES_TGZ_NAME, PACKAGE_TGZ_NAME
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, TestServer, \
    TurboTestClient, GenConanfile
from conans.util.files import gzopen_without_timestamps, is_dirty, save

conanfile = """from conans import ConanFile
class MyPkg(ConanFile):
    name = "Hello0"
    version = "1.2.1"
    exports_sources = "*"

    def package(self):
        self.copy("*")
"""

conanfile_upload_query = """from conans import ConanFile
class MyPkg(ConanFile):
    name = "Hello1"
    version = "1.2.1"
    exports_sources = "*"
    settings = "os", "arch"

    def package(self):
        self.copy("*")
"""


class UploadTest(unittest.TestCase):

    @attr("artifactory_ready")
    def test_upload_force(self):
        ref = ConanFileReference.loads("Hello/0.1@conan/testing")
        client = TurboTestClient(servers={"default": TestServer()})
        pref = client.create(ref, conanfile=GenConanfile().with_package_file("myfile.sh", "foo"))
        client.run("upload * --all --confirm")
        self.assertIn("Uploading conan_package.tgz", client.out)
        client.run("upload * --all --confirm")
        self.assertNotIn("Uploading conan_package.tgz", client.out)

        package_folder = client.cache.package_layout(pref.ref).package(pref)
        package_file_path = os.path.join(package_folder, "myfile.sh")

        if platform.system() == "Linux":
            client.run("remove '*' -f")
            client.create(ref, conanfile=GenConanfile().with_package_file("myfile.sh", "foo"))
            os.system('chmod +x "{}"'.format(package_file_path))
            self.assertTrue(os.stat(package_file_path).st_mode & stat.S_IXUSR)
            client.run("upload * --all --confirm")
            self.assertNotIn("Uploading conan_package.tgz", client.out)
            self.assertIn("Package is up to date, upload skipped", client.out)
            self.assertIn("Compressing package...", client.out)

        client.run("upload * --all --confirm --force")
        self.assertIn("Uploading conanfile.py", client.out)
        self.assertIn("Uploading conan_package.tgz", client.out)

        if platform.system() == "Linux":
            client.run("remove '*' -f")
            client.run("install {}".format(ref))
            # Owner with execute permissions
            self.assertTrue(os.stat(package_file_path).st_mode & stat.S_IXUSR)

    def test_upload_not_existing(self):
        client = TestClient(servers={"default": TestServer()},
                            users={"default": [("lasote", "mypass")]})
        client.save({"conanfile.py": GenConanfile()})
        client.run("export . Hello/0.1@lasote/testing")
        client.run("upload Hello/0.1@lasote/testing -p=123", assert_error=True)
        self.assertIn("ERROR: Binary package Hello/0.1@lasote/testing:123 not found", client.out)

    def not_existing_error_test(self):
        """ Trying to upload with pattern not matched must raise an Error
        """
        client = TestClient()
        client.run("upload some_nonsense", assert_error=True)
        self.assertIn("ERROR: No packages found matching pattern 'some_nonsense'",
                      client.out)

    def invalid_reference_error_test(self):
        """ Trying to upload an invalid reference must raise an Error
        """
        client = TestClient()
        client.run("upload some_nonsense -p hash1", assert_error=True)
        self.assertIn("ERROR: -p parameter only allowed with a valid recipe reference",
                      client.out)

    def non_existing_recipe_error_test(self):
        """ Trying to upload a non-existing recipe must raise an Error
        """
        client = TestClient(servers={"default": TestServer()})
        client.run("upload Pkg/0.1@user/channel", assert_error=True)
        self.assertIn("Recipe not found: 'Pkg/0.1@user/channel'", client.out)

    def non_existing_package_error_test(self):
        """ Trying to upload a non-existing package must raise an Error
        """
        servers = {"default": TestServer()}
        client = TestClient(servers=servers)
        client.run("upload Pkg/0.1@user/channel -p hash1", assert_error=True)
        self.assertIn("ERROR: Recipe not found: 'Pkg/0.1@user/channel'", client.out)

    def deprecated_p_arg_test(self):
        client = self._client()
        client.save({"conanfile.py": conanfile})
        client.run("create . user/testing")
        client.run("upload Hello0/1.2.1@user/testing -p {} -c".format(NO_SETTINGS_PACKAGE_ID))
        self.assertIn("WARN: Usage of `--package` argument is deprecated. "
                      "Use a full reference instead: `conan upload [...] "
                      "Hello0/1.2.1@user/testing:{}`".format(NO_SETTINGS_PACKAGE_ID), client.out)

    def upload_with_pref_test(self):
        client = self._client()
        client.save({"conanfile.py": conanfile})
        client.run("create . user/testing")
        client.run("upload Hello0/1.2.1@user/testing:{} -c".format(NO_SETTINGS_PACKAGE_ID))
        self.assertNotIn("WARN: Usage of `--package` argument is deprecated. "
                         "Use a full reference instead: `conan upload [...] "
                         "Hello0/1.2.1@user/testing:{}`".format(NO_SETTINGS_PACKAGE_ID),
                         client.out)
        self.assertIn("Uploading package 1/1: {} to 'default'".format(NO_SETTINGS_PACKAGE_ID),
                      client.out)

    def upload_with_pref_and_p_test(self):
        client = self._client()
        client.save({"conanfile.py": conanfile})
        client.run("create . user/testing")
        client.run("upload Hello0/1.2.1@user/testing:{} -c -p {}".format(NO_SETTINGS_PACKAGE_ID,
                                                                         NO_SETTINGS_PACKAGE_ID),
                   assert_error=True)

        self.assertIn("Use a full package reference (preferred) or the "
                      "`--package` command argument, but not both.", client.out)

    def _client(self):
        if not hasattr(self, "_servers"):
            servers = {}
            test_server = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")],
                                     users={"lasote": "mypass"})
            servers["default"] = test_server
            self._servers = servers
        client = TestClient(servers=self._servers, users={"default": [("lasote", "mypass")]})
        return client

    def pattern_upload_test(self):
        client = self._client()
        client.save({"conanfile.py": conanfile})
        client.run("create . user/testing")
        client.run("upload Hello0/*@user/testing --confirm --all")
        self.assertIn("Uploading conanmanifest.txt", client.out)
        self.assertIn("Uploading conan_package.tgz", client.out)
        self.assertIn("Uploading conanfile.py", client.out)

    def query_upload_test(self):
        client = self._client()
        client.save({"conanfile.py": conanfile_upload_query})

        for _os, arch in itertools.product(["Macos", "Linux", "Windows"],
                                           ["armv8", "x86_64"]):
            client.run("create . user/testing -s os=%s -s arch=%s" % (_os, arch))

        # Check that the right number of packages are picked up by the queries
        client.run("upload Hello1/*@user/testing --confirm -q 'os=Windows or os=Macos'")
        for i in range(1, 5):
            self.assertIn("Uploading package %d/4" % i, client.out)
        self.assertNotIn("Package is up to date, upload skipped", client.out)

        client.run("upload Hello1/*@user/testing --confirm -q 'os=Linux and arch=x86_64'")
        self.assertIn("Uploading package 1/1", client.out)

        client.run("upload Hello1/*@user/testing --confirm -q 'arch=armv8'")
        for i in range(1, 4):
            self.assertIn("Uploading package %d/3" % i, client.out)
        self.assertIn("Package is up to date, upload skipped", client.out)

        # Check that a query not matching any packages doesn't upload any packages
        client.run("upload Hello1/*@user/testing --confirm -q 'arch=sparc'")
        self.assertNotIn("Uploading package", client.out)

        # Check that an invalid query fails
        client.run("upload Hello1/*@user/testing --confirm -q 'blah blah blah'", assert_error=True)
        self.assertIn("Invalid package query", client.out)

    def broken_sources_tgz_test(self):
        # https://github.com/conan-io/conan/issues/2854
        client = self._client()
        client.save({"conanfile.py": conanfile,
                     "source.h": "my source"})
        client.run("create . user/testing")
        ref = ConanFileReference.loads("Hello0/1.2.1@user/testing")

        def gzopen_patched(name, mode="r", fileobj=None, compresslevel=None, **kwargs):
            raise ConanException("Error gzopen %s" % name)
        with mock.patch('conans.client.cmd.uploader.gzopen_without_timestamps',
                        new=gzopen_patched):
            client.run("upload * --confirm", assert_error=True)
            self.assertIn("ERROR: Error gzopen conan_sources.tgz", client.out)

            export_folder = client.cache.package_layout(ref).export()
            tgz = os.path.join(export_folder, EXPORT_SOURCES_TGZ_NAME)
            self.assertTrue(os.path.exists(tgz))
            self.assertTrue(is_dirty(tgz))

        client.run("upload * --confirm")
        self.assertIn("WARN: Hello0/1.2.1@user/testing: Removing conan_sources.tgz, "
                      "marked as dirty", client.out)
        self.assertTrue(os.path.exists(tgz))
        self.assertFalse(is_dirty(tgz))

    def broken_package_tgz_test(self):
        # https://github.com/conan-io/conan/issues/2854
        client = self._client()
        client.save({"conanfile.py": conanfile,
                     "source.h": "my source"})
        client.run("create . user/testing")
        pref = PackageReference.loads("Hello0/1.2.1@user/testing:" + NO_SETTINGS_PACKAGE_ID)

        def gzopen_patched(name, mode="r", fileobj=None, compresslevel=None, **kwargs):
            if name == PACKAGE_TGZ_NAME:
                raise ConanException("Error gzopen %s" % name)
            return gzopen_without_timestamps(name, mode, fileobj, compresslevel, **kwargs)
        with mock.patch('conans.client.cmd.uploader.gzopen_without_timestamps',
                        new=gzopen_patched):
            client.run("upload * --confirm --all", assert_error=True)
            self.assertIn("ERROR: Error gzopen conan_package.tgz", client.out)

            export_folder = client.cache.package_layout(pref.ref).package(pref)
            tgz = os.path.join(export_folder, PACKAGE_TGZ_NAME)
            self.assertTrue(os.path.exists(tgz))
            self.assertTrue(is_dirty(tgz))

        client.run("upload * --confirm --all")
        self.assertIn("WARN: Hello0/1.2.1@user/testing:%s: "
                      "Removing conan_package.tgz, marked as dirty" % NO_SETTINGS_PACKAGE_ID,
                      client.out)
        self.assertTrue(os.path.exists(tgz))
        self.assertFalse(is_dirty(tgz))

    def corrupt_upload_test(self):
        client = self._client()

        client.save({"conanfile.py": conanfile,
                     "include/hello.h": ""})
        client.run("create . frodo/stable")
        ref = ConanFileReference.loads("Hello0/1.2.1@frodo/stable")
        packages_folder = client.cache.package_layout(ref).packages()
        pkg_id = os.listdir(packages_folder)[0]
        package_folder = os.path.join(packages_folder, pkg_id)
        save(os.path.join(package_folder, "added.txt"), "")
        os.remove(os.path.join(package_folder, "include/hello.h"))
        client.run("upload Hello0/1.2.1@frodo/stable --all --check", assert_error=True)
        self.assertIn("WARN: Mismatched checksum 'added.txt'", client.out)
        self.assertIn("WARN: Mismatched checksum 'include/hello.h'", client.out)
        self.assertIn("ERROR: Cannot upload corrupted package", client.out)

    def upload_modified_recipe_test(self):
        client = self._client()

        client.save({"conanfile.py": conanfile,
                     "hello.cpp": "int i=0"})
        client.run("export . frodo/stable")
        client.run("upload Hello0/1.2.1@frodo/stable")
        self.assertIn("Uploading conanmanifest.txt", client.out)
        self.assertIn("Uploaded conan recipe 'Hello0/1.2.1@frodo/stable' to 'default'",
                      client.out)

        client2 = self._client()
        client2.save({"conanfile.py": conanfile + "\r\n#end",
                      "hello.cpp": "int i=1"})
        client2.run("export . frodo/stable")
        ref = ConanFileReference.loads("Hello0/1.2.1@frodo/stable")
        manifest = client2.cache.package_layout(ref).recipe_manifest()
        manifest.time += 10
        manifest.save(client2.cache.package_layout(ref).export())
        client2.run("upload Hello0/1.2.1@frodo/stable")
        self.assertIn("Uploading conanmanifest.txt", client2.out)
        self.assertIn("Uploaded conan recipe 'Hello0/1.2.1@frodo/stable' to 'default'",
                      client2.out)

        # first client tries to upload again
        if not client.cache.config.revisions_enabled:
            client.run("upload Hello0/1.2.1@frodo/stable", assert_error=True)
            self.assertIn("Remote recipe is newer than local recipe", client.out)
            self.assertIn("Local 'conanfile.py' using '\\n' line-ends", client.out)
            self.assertIn("Remote 'conanfile.py' using '\\r\\n' line-ends", client.out)
        else:
            # The client tries to upload exactly the same revision already uploaded, so no changes
            client.run("upload Hello0/1.2.1@frodo/stable")
            self.assertIn("Recipe is up to date, upload skipped", client.out)

    def upload_unmodified_recipe_test(self):
        client = self._client()

        files = cpp_hello_conan_files("Hello0", "1.2.1", build=False)
        client.save(files)
        client.run("export . frodo/stable")
        client.run("upload Hello0/1.2.1@frodo/stable")
        self.assertIn("Uploading conanmanifest.txt", client.out)
        self.assertIn("Uploaded conan recipe 'Hello0/1.2.1@frodo/stable' to 'default'",
                      client.out)

        client2 = self._client()
        client2.save(files)
        client2.run("export . frodo/stable")
        ref = ConanFileReference.loads("Hello0/1.2.1@frodo/stable")
        manifest = client2.cache.package_layout(ref).recipe_manifest()
        manifest.time += 10
        manifest.save(client2.cache.package_layout(ref).export())
        client2.run("upload Hello0/1.2.1@frodo/stable")
        self.assertNotIn("Uploading conanmanifest.txt", client2.out)
        self.assertNotIn("Uploaded conan recipe 'Hello0/1.2.1@frodo/stable' to 'default'",
                         client2.out)
        self.assertIn("Recipe is up to date, upload skipped", client2.out)

        # first client tries to upload again
        client.run("upload Hello0/1.2.1@frodo/stable")
        self.assertNotIn("Uploading conanmanifest.txt", client.out)
        self.assertNotIn("Uploaded conan recipe 'Hello0/1.2.1@frodo/stable' to 'default'",
                         client.out)
        self.assertIn("Recipe is up to date, upload skipped", client.out)

    def upload_unmodified_package_test(self):
        client = self._client()

        client.save({"conanfile.py": conanfile,
                     "hello.cpp": ""})
        client.run("create . frodo/stable")
        client.run("upload Hello0/1.2.1@frodo/stable --all")

        client2 = self._client()
        client2.save({"conanfile.py": conanfile,
                      "hello.cpp": ""})
        client2.run("create . frodo/stable")
        client2.run("upload Hello0/1.2.1@frodo/stable --all")
        self.assertIn("Recipe is up to date, upload skipped", client2.out)
        self.assertNotIn("Uploading conanfile.py", client2.out)
        self.assertNotIn("Uploading conan_sources.tgz", client2.out)
        self.assertNotIn("Uploaded conan recipe 'Hello0/1.2.1@frodo/stable' to 'default'",
                         client2.out)
        self.assertNotIn("Uploading conaninfo.txt", client2.out)  # conaninfo NOT changed
        self.assertNotIn("Uploading conan_package.tgz", client2.out)
        self.assertIn("Package is up to date, upload skipped", client2.out)

        # first client tries to upload again
        client.run("upload Hello0/1.2.1@frodo/stable --all")
        self.assertIn("Recipe is up to date, upload skipped", client.out)
        self.assertNotIn("Uploading conanfile.py", client.out)
        self.assertNotIn("Uploading conan_sources.tgz", client.out)
        self.assertNotIn("Uploaded conan recipe 'Hello0/1.2.1@frodo/stable' to 'default'",
                         client.out)
        self.assertNotIn("Uploading conaninfo.txt", client.out)  # conaninfo NOT changed
        self.assertNotIn("Uploading conan_package.tgz", client2.out)
        self.assertIn("Package is up to date, upload skipped", client2.out)

    def no_overwrite_argument_collision_test(self):
        client = self._client()
        client.save({"conanfile.py": conanfile,
                     "hello.cpp": ""})
        client.run("create . frodo/stable")

        # Not valid values as arguments
        client.run("upload Hello0/1.2.1@frodo/stable --no-overwrite kk", assert_error=True)
        self.assertIn("ERROR", client.out)

        # --force not valid with --no-overwrite
        client.run("upload Hello0/1.2.1@frodo/stable --no-overwrite --force", assert_error=True)
        self.assertIn("ERROR: '--no-overwrite' argument cannot be used together with '--force'",
                      client.out)

    def upload_no_overwrite_all_test(self):
        conanfile_new = """from conans import ConanFile, tools
class MyPkg(ConanFile):
    name = "Hello0"
    version = "1.2.1"
    exports_sources = "*"
    options = {"shared": [True, False]}
    default_options = "shared=False"

    def build(self):
        if tools.get_env("MY_VAR", False):
            open("file.h", 'w').close()

    def package(self):
        self.copy("*.h")
"""
        client = self._client()
        client.save({"conanfile.py": conanfile_new,
                     "hello.h": "",
                     "hello.cpp": ""})
        client.run("create . frodo/stable")

        # First time upload
        client.run("upload Hello0/1.2.1@frodo/stable --all --no-overwrite")
        self.assertNotIn("Forbidden overwrite", client.out)
        self.assertIn("Uploading Hello0/1.2.1@frodo/stable", client.out)

        # CASE: Upload again
        client.run("upload Hello0/1.2.1@frodo/stable --all --no-overwrite")
        self.assertIn("Recipe is up to date, upload skipped", client.out)
        self.assertIn("Package is up to date, upload skipped", client.out)
        self.assertNotIn("Forbidden overwrite", client.out)

        # CASE: Without changes
        client.run("create . frodo/stable")
        # upload recipe and packages
        client.run("upload Hello0/1.2.1@frodo/stable --all --no-overwrite")
        self.assertIn("Recipe is up to date, upload skipped", client.out)
        self.assertIn("Package is up to date, upload skipped", client.out)
        self.assertNotIn("Forbidden overwrite", client.out)

        # CASE: When recipe and package changes
        new_recipe = conanfile_new.replace("self.copy(\"*.h\")",
                                           "self.copy(\"*.h\")\n        self.copy(\"*.cpp\")")
        client.save({"conanfile.py": new_recipe})
        client.run("create . frodo/stable")
        # upload recipe and packages
        # *1
        client.run("upload Hello0/1.2.1@frodo/stable --all --no-overwrite",
                   assert_error=not client.cache.config.revisions_enabled)
        if not client.cache.config.revisions_enabled:
            # The --no-overwrite makes no sense with revisions
            self.assertIn("Forbidden overwrite", client.out)
            self.assertNotIn("Uploading conan_package.tgz", client.out)

        # CASE: When package changes
        client.run("upload Hello0/1.2.1@frodo/stable --all")
        with environment_append({"MY_VAR": "True"}):
            client.run("create . frodo/stable")
        # upload recipe and packages
        client.run("upload Hello0/1.2.1@frodo/stable --all --no-overwrite",
                   assert_error=not client.cache.config.revisions_enabled)
        if not client.cache.config.revisions_enabled:
            self.assertIn("Recipe is up to date, upload skipped", client.out)
            self.assertIn("ERROR: Local package is different from the remote package", client.out)
            self.assertIn("Forbidden overwrite", client.out)
            self.assertNotIn("Uploading conan_package.tgz", client.out)
        else:
            self.assertIn("Uploading conan_package.tgz", client.out)

    def upload_no_overwrite_recipe_test(self):
        conanfile_new = """from conans import ConanFile, tools
class MyPkg(ConanFile):
    name = "Hello0"
    version = "1.2.1"
    exports_sources = "*"
    options = {"shared": [True, False]}
    default_options = "shared=False"

    def build(self):
        if tools.get_env("MY_VAR", False):
            open("file.h", 'w').close()

    def package(self):
        self.copy("*.h")
"""
        client = self._client()
        client.save({"conanfile.py": conanfile_new,
                     "hello.h": "",
                     "hello.cpp": ""})
        client.run("create . frodo/stable")

        # First time upload
        client.run("upload Hello0/1.2.1@frodo/stable --all --no-overwrite recipe")
        self.assertNotIn("Forbidden overwrite", client.out)
        self.assertIn("Uploading Hello0/1.2.1@frodo/stable", client.out)

        # Upload again
        client.run("upload Hello0/1.2.1@frodo/stable --all --no-overwrite recipe")
        self.assertIn("Recipe is up to date, upload skipped", client.out)
        self.assertIn("Package is up to date, upload skipped", client.out)
        self.assertNotIn("Forbidden overwrite", client.out)

        # Create without changes
        # *1
        client.run("create . frodo/stable")
        client.run("upload Hello0/1.2.1@frodo/stable --all --no-overwrite recipe")
        self.assertIn("Recipe is up to date, upload skipped", client.out)
        self.assertIn("Package is up to date, upload skipped", client.out)
        self.assertNotIn("Forbidden overwrite", client.out)

        # Create with recipe and package changes
        new_recipe = conanfile_new.replace("self.copy(\"*.h\")",
                                           "self.copy(\"*.h\")\n        self.copy(\"*.cpp\")")
        client.save({"conanfile.py": new_recipe})
        client.run("create . frodo/stable")
        # upload recipe and packages
        client.run("upload Hello0/1.2.1@frodo/stable --all --no-overwrite recipe",
                   assert_error=not client.cache.config.revisions_enabled)
        if not client.cache.config.revisions_enabled:
            self.assertIn("Forbidden overwrite", client.out)
            self.assertNotIn("Uploading package", client.out)

            # Create with package changes
            client.run("upload Hello0/1.2.1@frodo/stable --all")
            with environment_append({"MY_VAR": "True"}):
                client.run("create . frodo/stable")
            # upload recipe and packages
            client.run("upload Hello0/1.2.1@frodo/stable --all --no-overwrite recipe")
            self.assertIn("Recipe is up to date, upload skipped", client.out)
            self.assertIn("Uploading conan_package.tgz", client.out)
            self.assertNotIn("Forbidden overwrite", client.out)
        else:
            self.assertIn("Uploading conan_package.tgz", client.out)

    def skip_upload_test(self):
        """ Check that the option --dry does not upload anything
        """
        client = self._client()

        files = cpp_hello_conan_files("Hello0", "1.2.1", build=False)
        client.save(files)
        client.run("export . frodo/stable")
        client.run("install Hello0/1.2.1@frodo/stable --build=missing")
        client.run("upload Hello0/1.2.1@frodo/stable -r default --all --skip-upload")

        # dry run should not upload
        self.assertNotIn("Uploading conan_package.tgz", client.out)

        # but dry run should compress
        self.assertIn("Compressing recipe...", client.out)
        self.assertIn("Compressing package...", client.out)

        client.run("search -r default")
        # after dry run nothing should be on the server ...
        self.assertNotIn("Hello0/1.2.1@frodo/stable", client.out)

        # now upload, the stuff should NOT be recompressed
        client.run("upload Hello0/1.2.1@frodo/stable -r default --all")

        # check for upload message
        self.assertIn("Uploading conan_package.tgz", client.out)

        # check if compressed files are re-used
        self.assertNotIn("Compressing recipe...", client.out)
        self.assertNotIn("Compressing package...", client.out)

        # now it should be on the server
        client.run("search -r default")
        self.assertIn("Hello0/1.2.1@frodo/stable", client.out)

    def upload_without_sources_test(self):
        client = self._client()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    pass
"""
        client.save({"conanfile.py": conanfile})
        client.run("create . Pkg/0.1@user/testing")
        client.run("upload * --all --confirm")
        client2 = self._client()
        client2.run("install Pkg/0.1@user/testing")
        client2.run("remote remove default")
        server2 = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")],
                             users={"lasote": "mypass"})
        client2.users = {"server2": [("lasote", "mypass")]}
        client2.servers = {"server2": server2}
        client2.update_servers()
        client2.run("upload * --all --confirm -r=server2")
        self.assertIn("Uploading conanfile.py", client2.out)
        self.assertIn("Uploading conan_package.tgz", client2.out)

    def upload_login_prompt_disabled_no_user_test(self):
        """ Without user info, uploads should fail when login prompt has been disabled.
        """
        files = cpp_hello_conan_files("Hello0", "1.2.1", build=False)
        client = self._client()
        client.save(files)
        client.run("config set general.non_interactive=True")
        client.run("create . user/testing")
        client.run("user -c")
        client.run("upload Hello0/1.2.1@user/testing", assert_error=True)

        self.assertIn('ERROR: Conan interactive mode disabled', client.out)
        self.assertNotIn("Uploading conanmanifest.txt", client.out)
        self.assertNotIn("Uploading conanfile.py", client.out)
        self.assertNotIn("Uploading conan_export.tgz", client.out)

    def upload_login_prompt_disabled_user_not_authenticated_test(self):
        """ When a user is not authenticated, uploads should fail when login prompt has been disabled.
        """
        files = cpp_hello_conan_files("Hello0", "1.2.1", build=False)
        client = self._client()
        client.save(files)
        client.run("config set general.non_interactive=True")
        client.run("create . user/testing")
        client.run("user -c")
        client.run("user lasote")
        client.run("upload Hello0/1.2.1@user/testing", assert_error=True)
        self.assertIn('ERROR: Conan interactive mode disabled', client.out)
        self.assertNotIn("Uploading conanmanifest.txt", client.out)
        self.assertNotIn("Uploading conanfile.py", client.out)
        self.assertNotIn("Uploading conan_export.tgz", client.out)
        self.assertNotIn("Please enter a password for \"lasote\" account:", client.out)

    def upload_login_prompt_disabled_user_authenticated_test(self):
        """ When a user is authenticated, uploads should work even when login prompt has been disabled.
        """
        files = cpp_hello_conan_files("Hello0", "1.2.1", build=False)
        client = self._client()
        client.save(files)
        client.run("config set general.non_interactive=True")
        client.run("create . user/testing")
        client.run("user -c")
        client.run("user lasote -p mypass")
        client.run("upload Hello0/1.2.1@user/testing")
        self.assertIn("Uploading conanmanifest.txt", client.out)
        self.assertIn("Uploading conanfile.py", client.out)
        self.assertIn("Uploading conan_export.tgz", client.out)

    def upload_key_error_test(self):
        files = cpp_hello_conan_files("Hello0", "1.2.1", build=False)
        server1 = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")], users={"lasote": "mypass"})
        server2 = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")], users={"lasote": "mypass"})
        servers = OrderedDict()
        servers["server1"] = server1
        servers["server2"] = server2
        client = TestClient(servers=servers)
        client.save(files)
        client.run("config set general.revisions_enabled=True")
        client.run("create . user/testing")
        client.run("user lasote -p mypass")
        client.run("user lasote -p mypass -r server2")
        client.run("upload Hello0/1.2.1@user/testing --all -r server1")
        client.run("remove * --force")
        client.run("install Hello0/1.2.1@user/testing -r server1")
        client.run("remote remove server1")
        client.run("upload Hello0/1.2.1@user/testing --all -r server2")
        self.assertNotIn("ERROR: 'server1'", client.out)

    def upload_export_pkg_test(self):
        """
        Package metadata created when doing an export-pkg and then uploading the package works
        """
        server1 = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")], users={"lasote": "mypass"})
        servers = OrderedDict()
        servers["server1"] = server1
        client = TestClient(servers=servers)
        client.save({"release/kk.lib": ""})
        client.run("user lasote -r server1 -p mypass")
        client.run("new hello/1.0 --header")
        client.run("export-pkg . user/testing -pf release")
        client.run("upload hello/1.0@user/testing --all -r server1")
        self.assertNotIn("Binary package hello/1.0@user/testing:5%s not found" %
                         NO_SETTINGS_PACKAGE_ID, client.out)
        ref = ConanFileReference("hello", "1.0", "user", "testing")
        metadata = client.cache.package_layout(ref).load_metadata()
        self.assertIn(NO_SETTINGS_PACKAGE_ID, metadata.packages)
        self.assertTrue(metadata.packages[NO_SETTINGS_PACKAGE_ID].revision)

    def test_no_remote_recipe_manifest(self):
        # https://github.com/conan-io/conan/issues/4953
        server = TestServer()
        servers = OrderedDict([("default", server)])
        client = TurboTestClient(servers=servers)
        client2 = TurboTestClient(servers=servers)

        ref = ConanFileReference.loads("lib/1.0@conan/testing")
        client.create(ref)
        complete_ref = client.upload_all(ref)
        # Simulate a missing manifest, maybe because it hasn't been uploaded yet
        export_folder = server.server_store.export(complete_ref)
        os.unlink(os.path.join(export_folder, "conanmanifest.txt"))

        # Upload same with client2
        client2.create(ref)
        client2.upload_all(ref)
        self.assertIn("WARN: The remote recipe doesn't have the 'conanmanifest.txt' file "
                      "and will be uploaded: 'lib/1.0@conan/testing'", client2.out)

    def test_concurrent_upload(self):
        # https://github.com/conan-io/conan/issues/4953
        server = TestServer()
        servers = OrderedDict([("default", server)])
        client = TurboTestClient(servers=servers)
        client2 = TurboTestClient(servers=servers)

        ref = ConanFileReference.loads("lib/1.0@conan/testing")
        client.create(ref)
        client.upload_all(ref)
        # The _check_recipe_date returns None, but later it will get the manifest ok
        with patch.object(CmdUpload, "_check_recipe_date") as check_date:
            check_date.return_value = None
            # Upload same with client2
            client2.create(ref)
            client2.run("upload lib/1.0@conan/testing")
            self.assertIn("Recipe is up to date, upload skipped", client2.out)
            self.assertNotIn("WARN", client2.out)

    def upload_with_pref_and_query_test(self):
        client = self._client()
        client.save({"conanfile.py": conanfile})
        client.run("create . user/testing")
        client.run("upload Hello0/1.2.1@user/testing:{} "
                   "-q 'os=Windows or os=Macos'".format(NO_SETTINGS_PACKAGE_ID),
                   assert_error=True)

        self.assertIn("'--query' argument cannot be used together with full reference", client.out)

    def upload_with_package_id_and_query_test(self):
        client = self._client()
        client.save({"conanfile.py": conanfile})
        client.run("create . user/testing")
        client.run("upload Hello0/1.2.1@user/testing -p {} "
                   "-q 'os=Windows or os=Macos'".format(NO_SETTINGS_PACKAGE_ID),
                   assert_error=True)

        self.assertIn("'--query' argument cannot be used together with '--package'", client.out)

    def upload_without_user_channel_test(self):
        server = TestServer(users={"user": "password"}, write_permissions=[("*/*@*/*", "*")])
        servers = {"default": server}
        client = TestClient(servers=servers, users={"default": [("user", "password")]})

        client.save({"conanfile.py": GenConanfile()})

        client.run('create . lib/1.0@')
        self.assertIn("lib/1.0: Package '{}' created".format(NO_SETTINGS_PACKAGE_ID), client.out)
        client.run('upload lib/1.0 -c --all')
        self.assertIn("Uploaded conan recipe 'lib/1.0' to 'default'", client.out)

        # Verify that in the remote it is stored as "_"
        pref = PackageReference.loads("lib/1.0@#0:{}#0".format(NO_SETTINGS_PACKAGE_ID))
        path = server.server_store.export(pref.ref)
        self.assertIn("/lib/1.0/_/_/0/export", path.replace("\\", "/"))

        path = server.server_store.package(pref)
        self.assertIn("/lib/1.0/_/_/0/package", path.replace("\\", "/"))

        # Should be possible with explicit package
        client.run('upload lib/1.0:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9')
        self.assertIn("Uploading package 1/1: 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 to 'default'",
                      client.out)
