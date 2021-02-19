import os
import shutil
import unittest

from conans import DEFAULT_REVISION_V1
from conans.client.tools.files import untargz
from conans.model.manifest import FileTreeManifest
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import EXPORT_TGZ_NAME
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.test_files import temp_folder, uncompress_packaged_files
from conans.test.utils.tools import TestClient, TestServer
from conans.util.files import load, save


class SynchronizeTest(unittest.TestCase):

    def test_upload(self):
        client = TestClient(servers={"default": TestServer()},
                            users={"default": [("lasote", "mypass")]})
        save(client.cache.default_profile_path, "")
        ref = ConanFileReference.loads("hello/0.1@lasote/stable#%s" % DEFAULT_REVISION_V1)
        files = {"conanfile.py": GenConanfile("hello", "0.1").with_exports("*"),
                 "to_be_deleted.txt": "delete me",
                 "to_be_deleted2.txt": "delete me2"}

        remote_paths = client.servers["default"].server_store

        client.save(files)
        client.run("export . lasote/stable")

        # Upload conan file
        client.run("upload %s" % str(ref))

        # Verify the files are there
        if client.cache.config.revisions_enabled:
            rev = client.cache.package_layout(ref).recipe_revision()
            ref = ref.copy_with_rev(rev)
        server_conan_path = remote_paths.export(ref)
        self.assertTrue(os.path.exists(os.path.join(server_conan_path, EXPORT_TGZ_NAME)))
        tmp = temp_folder()
        untargz(os.path.join(server_conan_path, EXPORT_TGZ_NAME), tmp)
        self.assertTrue(load(os.path.join(tmp, "to_be_deleted.txt")), "delete me")
        self.assertTrue(load(os.path.join(tmp, "to_be_deleted2.txt")), "delete me2")

        # Now delete local files export and upload and check that they are not in server
        os.remove(os.path.join(client.current_folder, "to_be_deleted.txt"))
        client.run("export . lasote/stable")
        client.run("upload %s" % str(ref))
        if client.cache.config.revisions_enabled:
            rev = client.cache.package_layout(ref).recipe_revision()
            ref = ref.copy_with_rev(rev)
        server_conan_path = remote_paths.export(ref)
        self.assertTrue(os.path.exists(os.path.join(server_conan_path, EXPORT_TGZ_NAME)))
        tmp = temp_folder()
        untargz(os.path.join(server_conan_path, EXPORT_TGZ_NAME), tmp)
        self.assertFalse(os.path.exists(os.path.join(tmp, "to_be_deleted.txt")))
        self.assertTrue(os.path.exists(os.path.join(tmp, "to_be_deleted2.txt")))

        # Now modify a file, and delete other, and put a new one.
        files["to_be_deleted2.txt"] = "modified content"
        files["new_file.lib"] = "new file"
        del files["to_be_deleted.txt"]
        client.save(files)
        client.run("export . lasote/stable")
        client.run("upload %s" % str(ref))

        if client.cache.config.revisions_enabled:
            rev = client.cache.package_layout(ref).recipe_revision()
            ref = ref.copy_with_rev(rev)
        server_conan_path = remote_paths.export(ref)

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

        client.run("install %s --build missing" % str(ref))
        # Upload package
        package_ids = client.cache.package_layout(ref).package_ids()
        client.run("upload %s -p %s" % (str(ref), str(package_ids[0])))

        # Check that package exists on server
        pref = PackageReference(ref, str(package_ids[0]))
        prev = remote_paths.get_last_package_revision(pref)
        pref = pref.copy_with_revs(pref.ref.revision, prev.revision)
        package_server_path = remote_paths.package(pref)
        self.assertTrue(os.path.exists(package_server_path))

        # Add a new file to package (artificially), upload again and check
        layout = client.cache.package_layout(pref.ref)
        pack_path = layout.package(pref)
        new_file_source_path = os.path.join(pack_path, "newlib.lib")
        save(new_file_source_path, "newlib")
        shutil.rmtree(layout.download_package(pref))  # Force new tgz

        self._create_manifest(client, pref)
        client.run("upload %s -p %s" % (str(ref), str(package_ids[0])))

        folder = uncompress_packaged_files(remote_paths, pref)
        remote_file_path = os.path.join(folder, "newlib.lib")
        self.assertTrue(os.path.exists(remote_file_path))

        # Now modify the file and check again
        save(new_file_source_path, "othercontent")
        self._create_manifest(client, pref)
        client.run("upload %s -p %s" % (str(ref), str(package_ids[0])))
        folder = uncompress_packaged_files(remote_paths, pref)
        remote_file_path = os.path.join(folder, "newlib.lib")
        self.assertTrue(os.path.exists(remote_file_path))
        self.assertTrue(load(remote_file_path), "othercontent")

        # Now delete the file and check again
        os.remove(new_file_source_path)
        self._create_manifest(client, pref)
        shutil.rmtree(layout.download_package(pref))  # Force new tgz
        client.run("upload %s -p %s" % (str(ref), str(package_ids[0])))
        folder = uncompress_packaged_files(remote_paths, pref)
        remote_file_path = os.path.join(folder, "newlib.lib")

        # With revisions makes no sense because there is a new revision always that sources change
        if not client.cache.config.revisions_enabled:
            self.assertFalse(os.path.exists(remote_file_path))
            self.assertNotEqual(remote_file_path, new_file_source_path)

    @staticmethod
    def _create_manifest(client, pref):
        # Create the manifest to be able to upload the package
        pack_path = client.cache.package_layout(pref.ref).package(pref)
        expected_manifest = FileTreeManifest.create(pack_path)
        expected_manifest.save(pack_path)
