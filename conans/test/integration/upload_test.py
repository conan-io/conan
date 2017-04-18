import unittest
from conans.test.utils.tools import TestServer, TestClient
from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
import os
from conans.test.utils.test_files import uncompress_packaged_files


class CompleteFlowTest(unittest.TestCase):

    def setUp(self):
        test_server = TestServer()
        self.servers = {"default": test_server}
        self.client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})

    def reuse_uploaded_tgz_test(self):
        '''Download packages from a remote, then copy to another channel
        and reupload them. Because they have not changed, the tgz is not created
        again'''

        # UPLOAD A PACKAGE
        conan_reference = ConanFileReference.loads("Hello0/0.1@lasote/stable")
        files = cpp_hello_conan_files("Hello0", "0.1", need_patch=True, build=False)
        files["another_export_file.lib"] = "to compress"
        self.client.save(files)
        self.client.run("export lasote/stable")
        self.client.run("install %s --build missing" % str(conan_reference))
        self.client.run("upload %s --all" % str(conan_reference))
        self.assertIn("Compressing recipe", self.client.user_io.out)
        self.assertIn("Compressing package", self.client.user_io.out)

        # UPLOAD TO A DIFFERENT CHANNEL WITHOUT COMPRESS AGAIN
        self.client.run("copy %s lasote/testing" % str(conan_reference))
        self.client.run("upload Hello0/0.1@lasote/testing --all")
        self.assertNotIn("Compressing recipe", self.client.user_io.out)
        self.assertNotIn("Compressing package", self.client.user_io.out)

    def reuse_downloaded_tgz_test(self):
        '''Download packages from a remote, then copy to another channel
        and reupload them. It needs to compress it again, not tgz is kept'''

        # UPLOAD A PACKAGE
        conan_reference = ConanFileReference.loads("Hello0/0.1@lasote/stable")
        files = cpp_hello_conan_files("Hello0", "0.1", need_patch=True, build=False)
        files["another_export_file.lib"] = "to compress"
        self.client.save(files)
        self.client.run("export lasote/stable")
        self.client.run("install %s --build missing" % str(conan_reference))
        self.client.run("upload %s --all" % str(conan_reference))
        self.assertIn("Compressing recipe", self.client.user_io.out)
        self.assertIn("Compressing package", self.client.user_io.out)

        # Other user downloads the package
        # THEN A NEW USER DOWNLOADS THE PACKAGES AND UPLOADS COMPRESSING AGAIN
        # BECAUSE ONLY TGZ IS KEPT WHEN UPLOADING
        other_client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        other_client.run("install Hello0/0.1@lasote/stable --all")
        other_client.run("upload Hello0/0.1@lasote/stable --all")
        self.assertIn("Compressing recipe", self.client.user_io.out)
        self.assertIn("Compressing package", self.client.user_io.out)

    def upload_only_tgz_if_needed_test(self):
        conan_reference = ConanFileReference.loads("Hello0/0.1@lasote/stable")
        files = cpp_hello_conan_files("Hello0", "0.1", need_patch=True, build=False)
        files["lib/another_export_file.lib"] = "to compress"
        self.client.save(files)
        self.client.run("export lasote/stable")
        self.client.run("install %s --build missing" % str(conan_reference))

        # Upload conans
        self.client.run("upload %s" % str(conan_reference))
        self.assertIn("Compressing recipe", str(self.client.user_io.out))

        # Not needed to tgz again
        self.client.run("upload %s" % str(conan_reference))
        self.assertNotIn("Compressing recipe", str(self.client.user_io.out))

        # Check that conans exists on server
        server_paths = self.servers["default"].paths
        conan_path = server_paths.export(conan_reference)
        self.assertTrue(os.path.exists(conan_path))
        package_ids = self.client.paths.conan_packages(conan_reference)
        package_ref = PackageReference(conan_reference, package_ids[0])

        # Upload package
        self.client.run("upload %s -p %s" % (str(conan_reference), str(package_ids[0])))
        self.assertIn("Compressing package", str(self.client.user_io.out))

        # Not needed to tgz again
        self.client.run("upload %s -p %s" % (str(conan_reference), str(package_ids[0])))
        self.assertNotIn("Compressing package", str(self.client.user_io.out))

        # If we install the package again will be removed and re tgz
        self.client.run("install %s --build missing" % str(conan_reference))
        # Upload package
        self.client.run("upload %s -p %s" % (str(conan_reference), str(package_ids[0])))
        self.assertNotIn("Compressing package", str(self.client.user_io.out))

        # Check library on server
        self._assert_library_exists_in_server(package_ref, server_paths)

    def _assert_library_exists_in_server(self, package_ref, paths):
        folder = uncompress_packaged_files(paths, package_ref)
        self._assert_library_files(folder)

    def _assert_library_files(self, path):
        libraries = os.listdir(os.path.join(path, "lib"))
        self.assertEquals(len(libraries), 1)
