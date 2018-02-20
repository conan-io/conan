import unittest
from conans.test.utils.tools import TestClient, TestServer
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.model.ref import ConanFileReference
from conans.util.files import save
import os


conanfile = """from conans import ConanFile
class MyPkg(ConanFile):
    name = "Hello0"
    version = "1.2.1"
    exports_sources = "*"

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
        save(client2.client_cache.digestfile_conanfile(ref), str(manifest))
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
        save(client2.client_cache.digestfile_conanfile(ref), str(manifest))
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
