import os
import unittest
from datetime import timedelta
from time import sleep

from conans import DEFAULT_REVISION_V1
from conans.errors import NotFoundException, RequestErrorException
from conans.model.manifest import FileTreeManifest
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import CONANINFO, CONAN_MANIFEST
from conans.server.crypto.jwt.jwt_updown_manager import JWTUpDownAuthManager
from conans.server.service.authorize import BasicAuthorizer
from conans.server.service.common.search import SearchService
from conans.server.service.v1.service import ConanService
from conans.server.service.v1.upload_download_service import FileUploadDownloadService
from conans.server.store.disk_adapter import ServerDiskAdapter
from conans.server.store.server_store import ServerStore
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.test_files import temp_folder
from conans.util.files import load, md5sum, mkdir, save, save_files


class MockFileSaver(object):

    def __init__(self, filename, content):
        self.filename = filename
        self.content = content

    def save(self, abspath):
        save(os.path.join(abspath, self.filename), self.content)


class FileUploadDownloadServiceTest(unittest.TestCase):

    def setUp(self):
        self.updown_auth_manager = JWTUpDownAuthManager("secret",
                                                        timedelta(seconds=1))

        self.storage_dir = temp_folder()
        self.service = FileUploadDownloadService(self.updown_auth_manager, self.storage_dir)
        self.disk_path = os.path.join(self.storage_dir, "dir", "other")
        self.relative_file_path = "dir/other/thefile.txt"
        self.absolute_file_path = os.path.join(self.disk_path, "thefile.txt")
        mkdir(self.disk_path)
        self.content = "the content"

    def test_file_download(self):
        save(os.path.join(self.disk_path, "thefile.txt"), self.content)
        token = self.updown_auth_manager.get_token_for(self.relative_file_path,
                                                       "pepe", len(self.content))
        path_to_file = self.service.get_file_path(self.relative_file_path, token)

        self.assertEqual(path_to_file, self.absolute_file_path)

        readed_content = load(self.absolute_file_path)
        self.assertEqual(readed_content, self.content)

        # Expire token
        sleep(2)
        self.assertRaises(NotFoundException, self.service.get_file_path,
                          self.relative_file_path, token)

    def test_file_upload(self):
        token = self.updown_auth_manager.get_token_for(self.relative_file_path,
                                                       "pepe", len(self.content))

        file_saver = MockFileSaver("thefile.txt", self.content)
        self.assertFalse(os.path.exists(self.absolute_file_path))
        self.service.put_file(file_saver, self.absolute_file_path, token, len(self.content))

        self.assertTrue(os.path.exists(self.absolute_file_path))

        # Raises if wrong size
        self.assertRaises(RequestErrorException, self.service.put_file, file_saver,
                          self.absolute_file_path, token, len(self.content) + 1)


class ConanServiceTest(unittest.TestCase):

    def setUp(self):
        self.ref = ConanFileReference.loads("openssl/2.0.3@lasote/testing#%s" % DEFAULT_REVISION_V1)

        self.pref = PackageReference(self.ref, "123123123", DEFAULT_REVISION_V1)
        self.tmp_dir = temp_folder()

        read_perms = [("*/*@*/*", "*")]
        write_perms = []
        authorizer = BasicAuthorizer(read_perms, write_perms)

        self.fake_url = "http://url"
        updown_auth_manager = JWTUpDownAuthManager("secret", timedelta(seconds=200))
        adapter = ServerDiskAdapter(self.fake_url, self.tmp_dir, updown_auth_manager)
        self.server_store = ServerStore(storage_adapter=adapter)
        self.service = ConanService(authorizer, self.server_store, "lasote")
        self.search_service = SearchService(authorizer, self.server_store, "lasote")

        files = {"conanfile.py": str(GenConanfile("test"))}
        save_files(self.server_store.export(self.ref), files)
        self.server_store.update_last_revision(self.ref)
        manifest = FileTreeManifest.create(self.server_store.export(self.ref))
        conan_digest_path = os.path.join(self.server_store.export(self.ref), CONAN_MANIFEST)
        save(conan_digest_path, repr(manifest))

        files = {"boost.lib": "", "boost2.lib": ""}
        save_files(self.server_store.package(self.pref), files)

    def test_get_recipe_snapshot(self):
        snap = self.service.get_recipe_snapshot(self.ref)
        base_path = self.server_store.export(self.ref)

        snap_expected = {'conanmanifest.txt': md5sum(os.path.join(base_path, "conanmanifest.txt")),
                         'conanfile.py': md5sum(os.path.join(base_path, "conanfile.py")),
                         }

        self.assertEqual(snap, snap_expected)

    def test_get_conanfile_download_urls(self):
        urls = self.service.get_conanfile_download_urls(self.ref)
        # Remove parameters
        urls = {name: url.split("?signature")[0] for name, url in urls.items()}

        def fake_url_build(filename):
            return (self.fake_url + "/"
                    + self.ref.dir_repr()
                    + "/" + self.ref.revision
                    + "/export/" + filename)

        expected_urls = {'conanfile.py': fake_url_build('conanfile.py'),
                         'conanmanifest.txt': fake_url_build('conanmanifest.txt')}
        self.assertEqual(urls, expected_urls)

    def test_get_package_download_urls(self):
        urls = self.service.get_package_download_urls(self.pref)
        # Remove parameters
        urls = {name: url.split("?signature")[0] for name, url in urls.items()}

        def fake_url_build(filename):
            return (self.fake_url
                    + "/" + self.pref.ref.dir_repr()
                    + "/" + self.pref.ref.revision
                    + "/package/" + self.pref.id
                    + "/" + self.pref.revision
                    + "/" + filename)

        expected_urls = {'boost.lib': fake_url_build('boost.lib'),
                         'boost2.lib': fake_url_build('boost2.lib')}
        self.assertEqual(urls, expected_urls)

    def test_get_conanfile_upload_urls(self):
        urls = self.service.get_conanfile_upload_urls(self.ref,
                                                      {"conanfile.py": 23,
                                                       "conanmanifest.txt": 24})
        # Remove parameters
        urls = {name: url.split("?signature")[0] for name, url in urls.items()}

        def fake_url_build(filename):
            return (self.fake_url
                    + "/" + self.ref.dir_repr()
                    + "/" + self.ref.revision
                    + "/export/" + filename)

        expected_urls = {'conanfile.py': fake_url_build('conanfile.py'),
                         'conanmanifest.txt': fake_url_build('conanmanifest.txt')}
        self.assertEqual(urls, expected_urls)

    def test_get_package_upload_urls(self):
        urls = self.service.get_package_upload_urls(self.pref, {"uno.lib": 23, "dos.dll": 24})
        # Remove parameters
        urls = {name: url.split("?signature")[0] for name, url in urls.items()}

        def fake_url_build(filename):
            return (self.fake_url
                    + "/" + self.pref.ref.dir_repr()
                    + "/" + self.pref.ref.revision
                    + "/package/" + self.pref.id
                    + "/" + self.pref.revision
                    + "/" + filename)

        expected_urls = {'uno.lib': fake_url_build('uno.lib'),
                         'dos.dll': fake_url_build('dos.dll')}
        self.assertEqual(urls, expected_urls)

    def test_search(self):
        """ check the dict is returned by get_packages_info service
        """
        # Creating and saving conans, packages, and conans.vars
        ref2 = ConanFileReference("openssl", "3.0", "lasote", "stable", DEFAULT_REVISION_V1)
        ref3 = ConanFileReference("Assimp", "1.10", "fenix", "stable", DEFAULT_REVISION_V1)
        ref4 = ConanFileReference("assimpFake", "0.1", "phil", "stable", DEFAULT_REVISION_V1)

        pref2 = PackageReference(ref2, "12345587754", DEFAULT_REVISION_V1)
        pref3 = PackageReference(ref3, "77777777777", DEFAULT_REVISION_V1)

        conan_vars = """
[options]
    use_Qt=%s
"""
        conan_vars1 = conan_vars % "True"
        conan_vars2 = conan_vars % "False"
        conan_vars3 = conan_vars % "True"

        save_files(self.server_store.package(self.pref), {CONANINFO: conan_vars1})
        self.server_store.update_last_package_revision(self.pref)
        save_files(self.server_store.package(pref2), {CONANINFO: conan_vars2})
        self.server_store.update_last_package_revision(pref2)
        save_files(self.server_store.package(pref3), {CONANINFO: conan_vars3})
        self.server_store.update_last_package_revision(pref3)

        save_files(self.server_store.export(ref4), {"dummy.txt": "//"})

        info = self.search_service.search()
        expected = [r.copy_clear_rev() for r in [ref3, ref4, self.ref, ref2]]
        self.assertEqual(expected, info)

        info = self.search_service.search(pattern="Assimp*", ignorecase=False)
        self.assertEqual(info, [ref3.copy_clear_rev()])

        info = self.search_service.search_packages(ref2, None)
        self.assertEqual(info, {'12345587754': {'content': '\n[options]\n    use_Qt=False\n',
                                                'full_requires': [],
                                                'options': {'use_Qt': 'False'},
                                                'recipe_hash': None,
                                                'settings': {}
                                                }})

        info = self.search_service.search_packages(ref3, None)
        self.assertEqual(info, {'77777777777': {'content': '\n[options]\n    use_Qt=True\n',
                                                'full_requires': [],
                                                'options': {'use_Qt': 'True'},
                                                'recipe_hash': None,
                                                'settings': {}}
                                })

    def test_remove(self):
        ref2 = ConanFileReference("OpenCV", "3.0", "lasote", "stable", DEFAULT_REVISION_V1)
        ref3 = ConanFileReference("Assimp", "1.10", "lasote", "stable", DEFAULT_REVISION_V1)

        pref2 = PackageReference(ref2, "12345587754", DEFAULT_REVISION_V1)
        pref3 = PackageReference(ref3, "77777777777", DEFAULT_REVISION_V1)

        save_files(self.server_store.export(ref2), {"fake.txt": "//fake"})
        self.server_store.update_last_revision(ref2)
        save_files(self.server_store.package(pref2), {"fake.txt": "//fake"})
        self.server_store.update_last_package_revision(pref2)
        save_files(self.server_store.package(pref3), {"fake.txt": "//fake"})
        self.server_store.update_last_package_revision(pref3)

        # Delete all the conans folder
        self.service.remove_conanfile(self.ref)
        conan_path = self.server_store.base_folder(self.ref)
        self.assertFalse(os.path.exists(conan_path))

        # Delete one package
        self.service.remove_packages(ref3, ["77777777777"])
        pref = PackageReference(ref3, '77777777777')
        package_folder_3 = self.server_store.package_revisions_root(pref)
        self.assertFalse(os.path.exists(package_folder_3))

        # Raise an exception
        self.assertRaises(NotFoundException,
                          self.service.remove_conanfile,
                          ConanFileReference("Fake", "1.0", "lasote", "stable"))
