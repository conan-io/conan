import unittest
from conans.test.utils.tools import TestServer, TestClient
from conans.model.ref import ConanFileReference, PackageReference
import os
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from nose.plugins.attrib import attr
from conans.util.files import load, save
from conans.test.utils.test_files import uncompress_packaged_files, temp_folder
from conans.paths import EXPORT_TGZ_NAME, CONAN_MANIFEST, PACKAGE_TGZ_NAME
from conans.tools import untargz
from conans.model.manifest import FileTreeManifest


@attr("slow")
class SynchronizeTest(unittest.TestCase):

    def setUp(self):
        test_server = TestServer()
        self.servers = {"default": test_server}
        self.client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})

    def upload_test(self):
        conan_reference = ConanFileReference.loads("Hello0/0.1@lasote/stable")
        files = cpp_hello_conan_files("Hello0", "0.1")
        files["to_be_deleted.txt"] = "delete me"
        files["to_be_deleted2.txt"] = "delete me2"

        remote_paths = self.client.servers["default"].paths
        server_conan_path = remote_paths.export(conan_reference)

        self.client.save(files)
        self.client.run("export . lasote/stable")

        # Upload conan file
        self.client.run("upload %s" % str(conan_reference))

        # Verify the files are there
        self.assertTrue(os.path.exists(os.path.join(server_conan_path, EXPORT_TGZ_NAME)))
        tmp = temp_folder()
        untargz(os.path.join(server_conan_path, EXPORT_TGZ_NAME), tmp)
        self.assertTrue(load(os.path.join(tmp, "to_be_deleted.txt")), "delete me")
        self.assertTrue(load(os.path.join(tmp, "to_be_deleted2.txt")), "delete me2")

        # Now delete local files export and upload and check that they are not in server
        os.remove(os.path.join(self.client.current_folder, "to_be_deleted.txt"))
        self.client.run("export . lasote/stable")
        self.client.run("upload %s" % str(conan_reference))
        self.assertTrue(os.path.exists(os.path.join(server_conan_path, EXPORT_TGZ_NAME)))
        tmp = temp_folder()
        untargz(os.path.join(server_conan_path, EXPORT_TGZ_NAME), tmp)
        self.assertFalse(os.path.exists(os.path.join(tmp, "to_be_deleted.txt")))
        self.assertTrue(os.path.exists(os.path.join(tmp, "to_be_deleted2.txt")))

        # Now modify a file, and delete other, and put a new one.
        files["to_be_deleted2.txt"] = "modified content"
        files["new_file.lib"] = "new file"
        del files["to_be_deleted.txt"]
        self.client.save(files)
        self.client.run("export . lasote/stable")
        self.client.run("upload %s" % str(conan_reference))

        # Verify all is correct
        self.assertTrue(os.path.exists(os.path.join(server_conan_path, EXPORT_TGZ_NAME)))
        tmp = temp_folder()
        untargz(os.path.join(server_conan_path, EXPORT_TGZ_NAME), tmp)
        self.assertTrue(load(os.path.join(tmp, "to_be_deleted2.txt")), "modified content")
        self.assertTrue(load(os.path.join(tmp, "new_file.lib")), "new file")
        self.assertFalse(os.path.exists(os.path.join(tmp, "to_be_deleted.txt")))

        ##########################
        # Now try with the package
        ##########################

        self.client.run("install %s --build missing" % str(conan_reference))
        # Upload package
        package_ids = self.client.paths.conan_packages(conan_reference)
        self.client.run("upload %s -p %s" % (str(conan_reference), str(package_ids[0])))

        # Check that conans exists on server
        package_reference = PackageReference(conan_reference, str(package_ids[0]))
        package_server_path = remote_paths.package(package_reference)
        self.assertTrue(os.path.exists(package_server_path))

        # Add a new file to package (artificially), upload again and check
        pack_path = self.client.paths.package(package_reference)
        new_file_source_path = os.path.join(pack_path, "newlib.lib")
        save(new_file_source_path, "newlib")
        os.unlink(os.path.join(pack_path, PACKAGE_TGZ_NAME))  # Force new tgz

        self._create_manifest(package_reference)
        self.client.run("upload %s -p %s" % (str(conan_reference), str(package_ids[0])))

        folder = uncompress_packaged_files(remote_paths, package_reference)
        remote_file_path = os.path.join(folder, "newlib.lib")
        self.assertTrue(os.path.exists(remote_file_path))

        # Now modify the file and check again
        save(new_file_source_path, "othercontent")
        self._create_manifest(package_reference)
        self.client.run("upload %s -p %s" % (str(conan_reference), str(package_ids[0])))
        folder = uncompress_packaged_files(remote_paths, package_reference)
        remote_file_path = os.path.join(folder, "newlib.lib")
        self.assertTrue(os.path.exists(remote_file_path))
        self.assertTrue(load(remote_file_path), "othercontent")

        # Now delete the file and check again
        os.remove(new_file_source_path)
        self._create_manifest(package_reference)
        os.unlink(os.path.join(pack_path, PACKAGE_TGZ_NAME))  # Force new tgz
        self.client.run("upload %s -p %s" % (str(conan_reference), str(package_ids[0])))
        folder = uncompress_packaged_files(remote_paths, package_reference)
        remote_file_path = os.path.join(folder, "newlib.lib")

        self.assertFalse(os.path.exists(remote_file_path))
        self.assertNotEquals(remote_file_path, new_file_source_path)

    def _create_manifest(self, package_reference):
        # Create the manifest to be able to upload the package
        pack_path = self.client.paths.package(package_reference)
        digest_path = self.client.client_cache.digestfile_package(package_reference)
        expected_manifest = FileTreeManifest.create(os.path.dirname(digest_path))
        save(os.path.join(pack_path, CONAN_MANIFEST), str(expected_manifest))
