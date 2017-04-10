import unittest
from conans.test.utils.tools import TestClient, TestServer
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.model.ref import ConanFileReference, PackageReference
from conans.util.files import save
import os


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

    def not_reupload_test(self):
        """ Check that if the package has not been modified, it is not uploaded
        again
        """
        servers = {}
        test_server = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")],
                                 users={"lasote": "mypass"})
        servers["default"] = test_server
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})

        files = cpp_hello_conan_files("Hello0", "1.2.1", build=False)
        client.save(files)
        client.run("export frodo/stable")
        client.run("install Hello0/1.2.1@frodo/stable --build=missing")
        client.run("upload Hello0/1.2.1@frodo/stable -r default --all")
        self.assertIn("Uploading conan_package.tgz", client.user_io.out)
        client.run("remove Hello0/1.2.1@frodo/stable -f")
        client.run("search")
        self.assertNotIn("Hello0/1.2.1@frodo/stable", client.user_io.out)
        client.run("install Hello0/1.2.1@frodo/stable")
        self.assertIn("Downloading conan_package.tgz", client.user_io.out)
        client.run("upload Hello0/1.2.1@frodo/stable -r default --all")
        self.assertIn("Uploaded conan recipe", client.user_io.out)
        self.assertNotIn("Uploading conan_package.tgz", client.user_io.out)
        self.assertIn("Package is up to date", client.user_io.out)

    def corrupt_upload_test(self):
        servers = {}
        test_server = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")],
                                 users={"lasote": "mypass"})
        servers["default"] = test_server
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})

        files = cpp_hello_conan_files("Hello0", "1.2.1", build=False)
        client.save(files)
        client.run("export frodo/stable")
        client.run("install Hello0/1.2.1@frodo/stable --build=missing")
        ref = ConanFileReference.loads("Hello0/1.2.1@frodo/stable")
        packages_folder = client.client_cache.packages(ref)
        pkg_id = os.listdir(packages_folder)[0]
        package_folder = os.path.join(packages_folder, pkg_id)
        save(os.path.join(package_folder, "added.txt"), "")
        os.remove(os.path.join(package_folder, "include/helloHello0.h"))
        error = client.run("upload Hello0/1.2.1@frodo/stable --all", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("WARN: Mismatched checksum 'added.txt'", client.user_io.out)
        self.assertIn("WARN: Mismatched checksum 'include/helloHello0.h'", client.user_io.out)
        self.assertIn("ERROR: Cannot upload corrupted package", client.user_io.out)

    def upload_newer_recipe_test(self):
        servers = {}
        test_server = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")],
                                 users={"lasote": "mypass"})
        servers["default"] = test_server
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})

        files = cpp_hello_conan_files("Hello0", "1.2.1", build=False)
        client.save(files)
        client.run("export frodo/stable")
        client.run("install Hello0/1.2.1@frodo/stable --build=missing")
        client.run("upload Hello0/1.2.1@frodo/stable --all")

        client2 = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        client2.save(files)
        client2.run("export frodo/stable")
        ref = ConanFileReference.loads("Hello0/1.2.1@frodo/stable")
        manifest = client2.client_cache.load_manifest(ref)
        manifest.time += 10
        save(client2.client_cache.digestfile_conanfile(ref), str(manifest))
        client2.run("install Hello0/1.2.1@frodo/stable --build=missing")
        client2.run("upload Hello0/1.2.1@frodo/stable --all")
        self.assertNotIn("conanfile", client2.user_io.out)
        self.assertIn("Package is up to date.", client2.user_io.out)
        self.assertIn("Uploading conanmanifest.txt", client2.user_io.out)

        # Now try again with the other client, which timestamp is older
        client.run("upload Hello0/1.2.1@frodo/stable --all")
        self.assertNotIn("conanfile", client2.user_io.out)
        self.assertIn("Package is up to date.", client2.user_io.out)
        self.assertIn("Uploading conanmanifest.txt", client.user_io.out)

    def skip_upload_test(self):
        """ Check that the option --dry does not upload anything
        """
        servers = {}
        test_server = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")],
                                 users={"lasote": "mypass"})
        servers["default"] = test_server
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})

        files = cpp_hello_conan_files("Hello0", "1.2.1", build=False)
        client.save(files)
        client.run("export frodo/stable")
        client.run("install Hello0/1.2.1@frodo/stable --build=missing")
        client.run("upload Hello0/1.2.1@frodo/stable -r default --all --skip_upload")

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
