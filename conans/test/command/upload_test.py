import unittest
from conans.tools import environment_append
from conans.test.utils.tools import TestClient, TestServer
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.model.ref import ConanFileReference, PackageReference
from conans.util.files import save, is_dirty, gzopen_without_timestamps
import os
import itertools
from mock import mock
from conans.errors import ConanException
from conans.paths import EXPORT_SOURCES_TGZ_NAME, PACKAGE_TGZ_NAME


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

    def not_existing_error_test(self):
        """ Trying to upload with pattern not matched must raise an Error
        """
        client = TestClient()
        error = client.run("upload some_nonsense", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: No packages found matching pattern 'some_nonsense'",
                      client.user_io.out)

    def invalid_reference_error_test(self):
        """ Trying to upload an invalid reference must raise an Error
        """
        client = TestClient()
        error = client.run("upload some_nonsense -p hash1", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: -p parameter only allowed with a valid recipe reference",
                      client.user_io.out)

    def non_existing_recipe_error_test(self):
        """ Trying to upload a non-existing recipe must raise an Error
        """
        client = TestClient()
        error = client.run("upload Pkg/0.1@user/channel", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: There is no local conanfile exported as Pkg/0.1@user/channel",
                      client.user_io.out)

    def non_existing_package_error_test(self):
        """ Trying to upload a non-existing package must raise an Error
        """
        client = TestClient()
        error = client.run("upload Pkg/0.1@user/channel -p hash1", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: There is no local conanfile exported as Pkg/0.1@user/channel",
                      client.user_io.out)

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
        self.assertIn("Uploading conanmanifest.txt", client.user_io.out)
        self.assertIn("Uploading conan_package.tgz", client.user_io.out)
        self.assertIn("Uploading conanfile.py", client.user_io.out)

    def query_upload_test(self):
        client = self._client()
        client.save({"conanfile.py": conanfile_upload_query})

        for os, arch in itertools.product(["Macos", "Linux", "Windows"],
                                          ["armv8", "x86_64"]):
            client.run("create . user/testing -s os=%s -s arch=%s" % (os, arch))

        # Check that the right number of packages are picked up by the queries
        client.run("upload Hello1/*@user/testing --confirm -q 'os=Windows or os=Macos'")
        for i in range(1, 5):
            self.assertIn("Uploading package %d/4" % i, client.user_io.out)
        self.assertNotIn("Package is up to date, upload skipped", client.user_io.out)

        client.run("upload Hello1/*@user/testing --confirm -q 'os=Linux and arch=x86_64'")
        self.assertIn("Uploading package 1/1", client.user_io.out)

        client.run("upload Hello1/*@user/testing --confirm -q 'arch=armv8'")
        for i in range(1, 4):
            self.assertIn("Uploading package %d/3" % i, client.user_io.out)
        self.assertIn("Package is up to date, upload skipped", client.user_io.out)

        # Check that a query not matching any packages doesn't upload any packages
        client.run("upload Hello1/*@user/testing --confirm -q 'arch=sparc'")
        self.assertNotIn("Uploading package", client.user_io.out)

        # Check that an invalid query fails
        try:
            client.run("upload Hello1/*@user/testing --confirm -q 'blah blah blah'")
        except:
            self.assertIn("Invalid package query", client.user_io.out)

    def broken_sources_tgz_test(self):
        # https://github.com/conan-io/conan/issues/2854
        client = self._client()
        client.save({"conanfile.py": conanfile,
                     "source.h": "my source"})
        client.run("create . user/testing")
        ref = ConanFileReference.loads("Hello0/1.2.1@user/testing")

        def gzopen_patched(name, mode="r", fileobj=None, compresslevel=None, **kwargs):
            raise ConanException("Error gzopen %s" % name)
        with mock.patch('conans.client.remote_manager.gzopen_without_timestamps', new=gzopen_patched):
            error = client.run("upload * --confirm", ignore_error=True)
            self.assertTrue(error)
            self.assertIn("ERROR: Error gzopen conan_sources.tgz", client.out)

            export_folder = client.client_cache.export(ref)
            tgz = os.path.join(export_folder, EXPORT_SOURCES_TGZ_NAME)
            self.assertTrue(os.path.exists(tgz))
            self.assertTrue(is_dirty(tgz))

        client.run("upload * --confirm")
        self.assertIn("WARN: Hello0/1.2.1@user/testing: Removing conan_sources.tgz, marked as dirty",
                      client.out)
        self.assertTrue(os.path.exists(tgz))
        self.assertFalse(is_dirty(tgz))

    def broken_package_tgz_test(self):
        # https://github.com/conan-io/conan/issues/2854
        client = self._client()
        client.save({"conanfile.py": conanfile,
                     "source.h": "my source"})
        client.run("create . user/testing")
        CONAN_PACKAGE_ID = "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"
        package_ref = PackageReference.loads("Hello0/1.2.1@user/testing:" +
                                             CONAN_PACKAGE_ID)

        def gzopen_patched(name, mode="r", fileobj=None, compresslevel=None, **kwargs):
            if name == PACKAGE_TGZ_NAME:
                raise ConanException("Error gzopen %s" % name)
            return gzopen_without_timestamps(name, mode, fileobj, compresslevel, **kwargs)
        with mock.patch('conans.client.remote_manager.gzopen_without_timestamps', new=gzopen_patched):
            error = client.run("upload * --confirm --all", ignore_error=True)
            self.assertTrue(error)
            self.assertIn("ERROR: Error gzopen conan_package.tgz", client.out)

            export_folder = client.client_cache.package(package_ref)
            tgz = os.path.join(export_folder, PACKAGE_TGZ_NAME)
            self.assertTrue(os.path.exists(tgz))
            self.assertTrue(is_dirty(tgz))

        client.run("upload * --confirm --all")
        self.assertIn("WARN: Hello0/1.2.1@user/testing:%s: "
                      "Removing conan_package.tgz, marked as dirty" % CONAN_PACKAGE_ID,
                      client.out)
        self.assertTrue(os.path.exists(tgz))
        self.assertFalse(is_dirty(tgz))

    def corrupt_upload_test(self):
        client = self._client()

        client.save({"conanfile.py": conanfile,
                     "include/hello.h": ""})
        client.run("create . frodo/stable")
        ref = ConanFileReference.loads("Hello0/1.2.1@frodo/stable")
        packages_folder = client.client_cache.packages(ref)
        pkg_id = os.listdir(packages_folder)[0]
        package_folder = os.path.join(packages_folder, pkg_id)
        save(os.path.join(package_folder, "added.txt"), "")
        os.remove(os.path.join(package_folder, "include/hello.h"))
        error = client.run("upload Hello0/1.2.1@frodo/stable --all --check", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("WARN: Mismatched checksum 'added.txt'", client.user_io.out)
        self.assertIn("WARN: Mismatched checksum 'include/hello.h'", client.user_io.out)
        self.assertIn("ERROR: Cannot upload corrupted package", client.user_io.out)

    def upload_modified_recipe_test(self):
        client = self._client()

        client.save({"conanfile.py": conanfile,
                     "hello.cpp": ""})
        client.run("export . frodo/stable")
        client.run("upload Hello0/1.2.1@frodo/stable")
        self.assertIn("Uploading conanmanifest.txt", client.user_io.out)
        self.assertIn("Uploaded conan recipe 'Hello0/1.2.1@frodo/stable' to 'default'",
                      client.out)

        client2 = self._client()

        client2.save({"conanfile.py": conanfile,
                     "hello.cpp": "//comamend"})
        client2.run("export . frodo/stable")
        ref = ConanFileReference.loads("Hello0/1.2.1@frodo/stable")
        manifest = client2.client_cache.load_manifest(ref)
        manifest.time += 10
        manifest.save(client2.client_cache.export(ref))
        client2.run("upload Hello0/1.2.1@frodo/stable")
        self.assertIn("Uploading conanmanifest.txt", client2.user_io.out)
        self.assertIn("Uploaded conan recipe 'Hello0/1.2.1@frodo/stable' to 'default'",
                      client2.out)

        # first client tries to upload again
        error = client.run("upload Hello0/1.2.1@frodo/stable", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Remote recipe is newer than local recipe", client.user_io.out)

    def upload_unmodified_recipe_test(self):
        client = self._client()

        files = cpp_hello_conan_files("Hello0", "1.2.1", build=False)
        client.save(files)
        client.run("export . frodo/stable")
        client.run("upload Hello0/1.2.1@frodo/stable")
        self.assertIn("Uploading conanmanifest.txt", client.user_io.out)
        self.assertIn("Uploaded conan recipe 'Hello0/1.2.1@frodo/stable' to 'default'",
                      client.out)

        client2 = self._client()
        client2.save(files)
        client2.run("export . frodo/stable")
        ref = ConanFileReference.loads("Hello0/1.2.1@frodo/stable")
        manifest = client2.client_cache.load_manifest(ref)
        manifest.time += 10
        manifest.save(client2.client_cache.export(ref))
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
        error = client.run("upload Hello0/1.2.1@frodo/stable --no-overwrite kk", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR", client.out)

        # --force not valid with --no-overwrite
        error = client.run("upload Hello0/1.2.1@frodo/stable --no-overwrite --force",
                           ignore_error=True)
        self.assertTrue(error)
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
        self.assertIn("Recipe is up to date, upload skipped", client.all_output)
        self.assertIn("Package is up to date, upload skipped", client.out)
        self.assertNotIn("Forbidden overwrite", client.out)

        # CASE: When recipe and package changes
        new_recipe = conanfile_new.replace("self.copy(\"*.h\")",
                                           "self.copy(\"*.h\")\n        self.copy(\"*.cpp\")")
        client.save({"conanfile.py": new_recipe})
        client.run("create . frodo/stable")
        # upload recipe and packages
        error = client.run("upload Hello0/1.2.1@frodo/stable --all --no-overwrite",
                           ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Forbidden overwrite", client.out)
        self.assertNotIn("Uploading package", client.out)

        # CASE: When package changes
        client.run("upload Hello0/1.2.1@frodo/stable --all")
        with environment_append({"MY_VAR": "True"}):
            client.run("create . frodo/stable")
        # upload recipe and packages
        error = client.run("upload Hello0/1.2.1@frodo/stable --all --no-overwrite",
                           ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Recipe is up to date, upload skipped", client.out)
        self.assertIn("ERROR: Local package is different from the remote package", client.out)
        self.assertIn("Forbidden overwrite", client.out)
        self.assertNotIn("Uploading conan_package.tgz", client.out)

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
        error = client.run("upload Hello0/1.2.1@frodo/stable --all --no-overwrite recipe",
                           ignore_error=True)
        self.assertTrue(error)
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
        self.assertNotIn("Uploading conan_package.tgz", client.user_io.out)

        # but dry run should compress
        self.assertIn("Compressing recipe...", client.user_io.out)
        self.assertIn("Compressing package...", client.user_io.out)

        client.run("search -r default")
        # after dry run nothing should be on the server ...
        self.assertNotIn("Hello0/1.2.1@frodo/stable", client.user_io.out)

        # now upload, the stuff should NOT be recompressed
        client.run("upload Hello0/1.2.1@frodo/stable -r default --all")

        # check for upload message
        self.assertIn("Uploading conan_package.tgz", client.user_io.out)

        # check if compressed files are re-used
        self.assertNotIn("Compressing recipe...", client.user_io.out)
        self.assertNotIn("Compressing package...", client.user_io.out)

        # now it should be on the server
        client.run("search -r default")
        self.assertIn("Hello0/1.2.1@frodo/stable", client.user_io.out)

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
        client2.update_servers({"server2": server2})
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
        error = client.run("upload Hello0/1.2.1@user/testing", ignore_error=True)
        self.assertTrue(error)
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
        error = client.run("upload Hello0/1.2.1@user/testing", ignore_error=True)
        self.assertTrue(error)
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
