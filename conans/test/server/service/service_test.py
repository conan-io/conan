import unittest
from conans.model.ref import ConanFileReference, PackageReference
from conans.server.service.service import ConanService, FileUploadDownloadService,\
    SearchService
from conans.paths import CONAN_MANIFEST, CONANINFO, SimplePaths
from conans.util.files import save_files, save, mkdir, load, md5sum
from conans.server.service.authorize import BasicAuthorizer
import os
from conans.errors import NotFoundException, RequestErrorException
from conans.test.utils.test_files import hello_source_files
from conans.server.store.file_manager import FileManager
from conans.server.crypto.jwt.jwt_updown_manager import JWTUpDownAuthManager
from datetime import timedelta
from time import sleep
from conans.model.manifest import FileTreeManifest
from conans.test.utils.test_files import temp_folder
from conans.server.store.disk_adapter import ServerDiskAdapter
from conans.search.search import DiskSearchManager, DiskSearchAdapter


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

        self.assertEquals(path_to_file, self.absolute_file_path)

        readed_content = load(self.absolute_file_path)
        self.assertEquals(readed_content, self.content)

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
        self.conan_reference = ConanFileReference.loads("openssl/2.0.3@lasote/testing")
        self.package_reference = PackageReference(self.conan_reference, "123123123")
        self.tmp_dir = temp_folder()

        read_perms = [("*/*@*/*", "*")]
        write_perms = []
        authorizer = BasicAuthorizer(read_perms, write_perms)

        self.fake_url = "http://url"
        updown_auth_manager = JWTUpDownAuthManager("secret",
                                                   timedelta(seconds=200))
        adapter = ServerDiskAdapter(self.fake_url, self.tmp_dir, updown_auth_manager)
        self.paths = SimplePaths(self.tmp_dir)
        self.file_manager = FileManager(self.paths, adapter)

        search_adapter = DiskSearchAdapter()
        self.search_manager = DiskSearchManager(self.paths, search_adapter)

        self.service = ConanService(authorizer, self.file_manager, "lasote")
        self.search_service = SearchService(authorizer, self.search_manager, "lasote")

        files = hello_source_files("test")
        save_files(self.paths.export(self.conan_reference), files)
        self.conan_digest = FileTreeManifest.create(self.paths.export(self.conan_reference))
        conan_digest_path = os.path.join(self.paths.export(self.conan_reference), CONAN_MANIFEST)
        save(conan_digest_path, str(self.conan_digest))

        files = hello_source_files("package")
        save_files(self.paths.package(self.package_reference), files)

    def test_get_conanfile_snapshot(self):
        snap = self.service.get_conanfile_snapshot(self.conan_reference)
        base_path = self.paths.export(self.conan_reference)

        snap_expected = {'hello.cpp': md5sum(os.path.join(base_path, "hello.cpp")),
                         'conanmanifest.txt': md5sum(os.path.join(base_path, "conanmanifest.txt")),
                         'executable': md5sum(os.path.join(base_path, "executable")),
                         'main.cpp':  md5sum(os.path.join(base_path, "main.cpp")),
                         'CMakeLists.txt':  md5sum(os.path.join(base_path, "CMakeLists.txt")),
                         'hellotest.h':  md5sum(os.path.join(base_path, "hellotest.h"))}

        self.assertEquals(snap, snap_expected)

    def test_get_conanfile_download_urls(self):
        urls = self.service.get_conanfile_download_urls(self.conan_reference)
        # Remove parameters
        urls = {name: url.split("?signature")[0] for name, url in urls.items()}

        def fake_url_build(filename):
            return self.fake_url + "/" + "/".join(self.conan_reference) + "/export/" + filename

        expected_urls = {'CMakeLists.txt': fake_url_build('CMakeLists.txt'),
                         'conanmanifest.txt': fake_url_build('conanmanifest.txt'),
                         'executable': fake_url_build('executable'),
                         'hello.cpp': fake_url_build('hello.cpp'),
                         'hellotest.h': fake_url_build('hellotest.h'),
                         'main.cpp': fake_url_build('main.cpp')}
        self.assertEquals(urls, expected_urls)

    def test_get_package_download_urls(self):
        urls = self.service.get_package_download_urls(self.package_reference)
        # Remove parameters
        urls = {name: url.split("?signature")[0] for name, url in urls.items()}

        def fake_url_build(filename):
            return self.fake_url + "/" + "/".join(self.package_reference.conan) \
                + "/package/" + self.package_reference.package_id + "/" + filename

        expected_urls = {'CMakeLists.txt': fake_url_build('CMakeLists.txt'),
                         'executable': fake_url_build('executable'),
                         'hello.cpp': fake_url_build('hello.cpp'),
                         'hellopackage.h': fake_url_build('hellopackage.h'),
                         'main.cpp': fake_url_build('main.cpp')}
        self.assertEquals(urls, expected_urls)

    def test_get_conanfile_upload_urls(self):
        urls = self.service.get_conanfile_upload_urls(self.conan_reference,
                                                      {"conanfile.py": 23,
                                                       "conanmanifest.txt": 24})
        # Remove parameters
        urls = {name: url.split("?signature")[0] for name, url in urls.items()}

        def fake_url_build(filename):
            return self.fake_url + "/" + "/".join(self.conan_reference) + "/export/" + filename

        expected_urls = {'conanfile.py': fake_url_build('conanfile.py'),
                         'conanmanifest.txt': fake_url_build('conanmanifest.txt')}
        self.assertEquals(urls, expected_urls)

    def test_get_package_upload_urls(self):
        urls = self.service.get_package_upload_urls(self.package_reference, {"uno.lib": 23,
                                                                             "dos.dll": 24})
        # Remove parameters
        urls = {name: url.split("?signature")[0] for name, url in urls.items()}

        def fake_url_build(filename):
            return self.fake_url + "/" + "/".join(self.package_reference.conan) \
                + "/package/" + self.package_reference.package_id + "/" + filename

        expected_urls = {'uno.lib': fake_url_build('uno.lib'),
                         'dos.dll': fake_url_build('dos.dll')}
        self.assertEquals(urls, expected_urls)

    def test_search(self):
        """ check the dict is returned by get_packages_info service
        """
        # Creating and saving conans, packages, and conans.vars
        conan_ref2 = ConanFileReference("openssl", "3.0", "lasote", "stable")
        conan_ref3 = ConanFileReference("Assimp", "1.10", "fenix", "stable")
        conan_ref4 = ConanFileReference("assimpFake", "0.1", "phil", "stable")

        package_ref2 = PackageReference(conan_ref2, "12345587754")
        package_ref3 = PackageReference(conan_ref3, "77777777777")

        conan_vars = """
[options]
    use_Qt=%s
"""
        conan_vars1 = conan_vars % "True"
        conan_vars2 = conan_vars % "False"
        conan_vars3 = conan_vars % "True"

        save_files(self.paths.package(self.package_reference), {CONANINFO: conan_vars1})
        save_files(self.paths.package(package_ref2), {CONANINFO: conan_vars2})
        save_files(self.paths.package(package_ref3), {CONANINFO: conan_vars3})
        save_files(self.paths.export(conan_ref4), {"dummy.txt": "//"})

        info = self.search_service.search()
        expected = [conan_ref3, conan_ref4, self.conan_reference, conan_ref2]
        self.assertEqual(expected, info)

        info = self.search_service.search(pattern="Assimp*", ignorecase=False)
        self.assertEqual(info, [conan_ref3])

        info = self.search_service.search_packages(conan_ref2, None)
        self.assertEqual(info, {'12345587754': {'full_requires': [],
                                                'options': {'use_Qt': 'False'},
                                                'settings': {},
                                                'recipe_hash': None}})

        info = self.search_service.search_packages(conan_ref3, None)
        self.assertEqual(info, {'77777777777': {'full_requires': [],
                                                'options': {'use_Qt': 'True'},
                                                'settings': {},
                                                'recipe_hash': None}})

    def remove_test(self):
        conan_ref2 = ConanFileReference("OpenCV", "3.0", "lasote", "stable")
        conan_ref3 = ConanFileReference("Assimp", "1.10", "lasote", "stable")

        package_ref2 = PackageReference(conan_ref2, "12345587754")
        package_ref3 = PackageReference(conan_ref3, "77777777777")

        save_files(self.paths.export(conan_ref2), {"fake.txt": "//fake"})
        save_files(self.paths.package(package_ref2), {"fake.txt": "//fake"})
        save_files(self.paths.package(package_ref3), {"fake.txt": "//fake"})

        # Delete all the conans folder
        self.service.remove_conanfile(self.conan_reference)
        conan_path = self.paths.conan(self.conan_reference)
        self.assertFalse(os.path.exists(conan_path))

        # Delete one package
        self.service.remove_packages(conan_ref3, ["77777777777"])
        package_folder_3 = self.paths.package(PackageReference(conan_ref3, '077777777777'))
        self.assertFalse(os.path.exists(package_folder_3))

        # Raise an exception
        self.assertRaises(NotFoundException,
                          self.service.remove_conanfile,
                          ConanFileReference("Fake", "1.0", "lasote", "stable"))
