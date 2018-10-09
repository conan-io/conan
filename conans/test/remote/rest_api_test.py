import os
import platform
import unittest

import requests
from nose.plugins.attrib import attr

from conans.client.rest.rest_client import RestApiClient
from conans.client.rest.rest_client_v1 import complete_url
from conans.model.info import ConanInfo
from conans.model.manifest import FileTreeManifest
from conans.model.ref import ConanFileReference, PackageReference
from conans.model.version import Version
from conans.paths import CONANFILE, CONAN_MANIFEST, CONANINFO
from conans.server.rest.bottle_plugins.version_checker import VersionCheckerPlugin
from conans.test.server.utils.server_launcher import TestServerLauncher
from conans.test.utils.test_files import hello_source_files
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestBufferConanOutput
from conans.util.files import md5, save


class RestApiUnitTest(unittest.TestCase):

    def relative_url_completion_test(self):

        # test absolute urls
        self.assertEquals(complete_url("http://host2", "http://host"), "http://host")
        self.assertEquals(complete_url("http://host2", "http://host:1234"), "http://host:1234")
        self.assertEquals(complete_url("http://host2", "https://host"), "https://host")
        self.assertEquals(complete_url("http://host2", "https://host:1234"), "https://host:1234")

        # test relative urls
        self.assertEquals(complete_url("http://host", "v1/path_to_file.txt"),
                          "http://host/v1/path_to_file.txt")

        self.assertEquals(complete_url("http://host:1234", "v1/path_to_file.txt"),
                          "http://host:1234/v1/path_to_file.txt")

        self.assertEquals(complete_url("https://host", "v1/path_to_file.txt"),
                          "https://host/v1/path_to_file.txt")

        self.assertEquals(complete_url("https://host:1234", "v1/path_to_file.txt"),
                          "https://host:1234/v1/path_to_file.txt")

        # test relative urls with subdirectory
        self.assertEquals(complete_url("https://host:1234/subdir/", "v1/path_to_file.txt"),
                          "https://host:1234/subdir/v1/path_to_file.txt")


@attr('slow')
@attr('rest_api')
class RestApiTest(unittest.TestCase):
    '''Open a real server (sockets) to test rest_api function.'''

    server = None
    api = None

    @classmethod
    def setUpClass(cls):
        if not cls.server:
            plugin = VersionCheckerPlugin(Version("0.16.0"), Version("0.16.0"), ["ImCool"])
            cls.server = TestServerLauncher(server_version=Version("0.16.0"),
                                            min_client_compatible_version=Version("0.16.0"),
                                            plugins=[plugin])
            cls.server.start()

            cls.api = RestApiClient(TestBufferConanOutput(), requester=requests)
            cls.api.remote_url = "http://127.0.0.1:%s" % str(cls.server.port)

            # Authenticate user
            token = cls.api.authenticate("private_user", "private_pass")
            cls.api.token = token

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def tearDown(self):
        RestApiTest.server.clean()

    def server_info_test(self):
        check, version, capabilities = self.api.server_info()
        self.assertEquals(version, "0.16.0")
        self.assertEquals(check, None)  # None because we are not sending client version
        self.assertEquals(capabilities, ["ImCool"])

    def get_conan_test(self):
        # Upload a conans
        conan_reference = ConanFileReference.loads("conan1/1.0.0@private_user/testing")
        self._upload_recipe(conan_reference)

        # Get the conans
        tmp_dir = temp_folder()
        self.api.get_recipe(conan_reference, tmp_dir)
        self.assertIn(CONANFILE, os.listdir(tmp_dir))
        self.assertIn(CONAN_MANIFEST, os.listdir(tmp_dir))

    def get_conan_manifest_test(self):
        # Upload a conans
        conan_reference = ConanFileReference.loads("conan2/1.0.0@private_user/testing")
        self._upload_recipe(conan_reference)

        # Get the conans digest
        digest = self.api.get_conan_manifest(conan_reference)
        self.assertEquals(digest.summary_hash, "34b389d4abf03f3b240ee4aa7cd9ac49")
        self.assertEquals(digest.time, 123123123)

    def get_package_test(self):
        # Upload a conans
        conan_reference = ConanFileReference.loads("conan3/1.0.0@private_user/testing")
        self._upload_recipe(conan_reference)

        # Upload an package
        package_reference = PackageReference(conan_reference, "1F23223EFDA")
        self._upload_package(package_reference)

        # Get the package
        tmp_dir = temp_folder()
        self.api.get_package(package_reference, tmp_dir)
        self.assertIn("hello.cpp", os.listdir(tmp_dir))

    def get_package_info_test(self):
        # Upload a conans
        conan_reference = ConanFileReference.loads("conan3/1.0.0@private_user/testing")
        self._upload_recipe(conan_reference)

        # Upload an package
        package_reference = PackageReference(conan_reference, "1F23223EFDA")
        conan_info = """[settings]
    arch=x86_64
    compiler=gcc
    os=Linux
[options]
    386=False
[requires]
    Hello
    Bye/2.9
    Say/2.1@user/testing
    Chat/2.1@user/testing:SHA_ABC
"""
        self._upload_package(package_reference, {CONANINFO: conan_info})

        # Get the package info
        info = self.api.get_package_info(package_reference)
        self.assertIsInstance(info, ConanInfo)
        self.assertEquals(info, ConanInfo.loads(conan_info))

    def upload_huge_conan_test(self):
        if platform.system() != "Windows":
            # Upload a conans
            conan_reference = ConanFileReference.loads("conanhuge/1.0.0@private_user/testing")
            files = {"file%s.cpp" % name: "File conent" for name in range(1000)}
            self._upload_recipe(conan_reference, files)

            # Get the conans
            tmp = temp_folder()
            files = self.api.get_recipe(conan_reference, tmp)
            self.assertIsNotNone(files)
            self.assertTrue(os.path.exists(os.path.join(tmp, "file999.cpp")))

    def search_test(self):
        # Upload a conan1
        conan_name1 = "HelloOnly/0.10@private_user/testing"
        conan_reference1 = ConanFileReference.loads(conan_name1)
        self._upload_recipe(conan_reference1)

        # Upload a package
        conan_info = """[settings]
    arch=x86_64
    compiler=gcc
    os=Linux
[options]
    386=False
[requires]
    Hello
    Bye/2.9
    Say/2.1@user/testing
    Chat/2.1@user/testing:SHA_ABC
"""
        package_reference = PackageReference(conan_reference1, "1F23223EFDA")
        self._upload_package(package_reference, {CONANINFO: conan_info})

        # Upload a conan2
        conan_name2 = "helloonlyToo/2.1@private_user/stable"
        conan_reference2 = ConanFileReference.loads(conan_name2)
        self._upload_recipe(conan_reference2)

        # Get the info about this ConanFileReference
        info = self.api.search_packages(conan_reference1, None)
        self.assertEqual(ConanInfo.loads(conan_info).serialize_min(), info["1F23223EFDA"])

        # Search packages
        results = self.api.search("HelloOnly*", ignorecase=False)

        self.assertEqual(results, [conan_reference1])

    def remove_test(self):
        # Upload a conans
        conan_reference1 = ConanFileReference.loads("MyFirstConan/1.0.0@private_user/testing")
        self._upload_recipe(conan_reference1)
        path1 = self.server.paths.conan(conan_reference1)
        self.assertTrue(os.path.exists(path1))
        # Remove conans and packages
        self.api.remove_conanfile(conan_reference1)
        self.assertFalse(os.path.exists(path1))

    def remove_packages_test(self):
        conan_ref = ConanFileReference.loads("MySecondConan/2.0.0@private_user/testing")
        self._upload_recipe(conan_ref)

        folders = {}
        for sha in ["1", "2", "3", "4", "5"]:
            # Upload an package
            package_ref = PackageReference(conan_ref, sha)
            self._upload_package(package_ref)
            folder = self.server.paths.package(package_ref)
            self.assertTrue(os.path.exists(folder))
            folders[sha] = folder

        self.api.remove_packages(conan_ref, ["1"])
        self.assertTrue(os.path.exists(self.server.paths.conan(conan_ref)))
        self.assertFalse(os.path.exists(folders["1"]))
        self.assertTrue(os.path.exists(folders["2"]))
        self.assertTrue(os.path.exists(folders["3"]))
        self.assertTrue(os.path.exists(folders["4"]))
        self.assertTrue(os.path.exists(folders["5"]))

        self.api.remove_packages(conan_ref, ["2", "3"])
        self.assertTrue(os.path.exists(self.server.paths.conan(conan_ref)))
        self.assertFalse(os.path.exists(folders["1"]))
        self.assertFalse(os.path.exists(folders["2"]))
        self.assertFalse(os.path.exists(folders["3"]))
        self.assertTrue(os.path.exists(folders["4"]))
        self.assertTrue(os.path.exists(folders["5"]))

        self.api.remove_packages(conan_ref, [])
        self.assertTrue(os.path.exists(self.server.paths.conan(conan_ref)))
        for sha in ["1", "2", "3", "4", "5"]:
            self.assertFalse(os.path.exists(folders[sha]))

    def _upload_package(self, package_reference, base_files=None):

        files = hello_source_files(3, [1, 12])
        if base_files:
            files.update(base_files)

        tmp_dir = temp_folder()
        abs_paths = {}
        for filename, content in files.items():
            abs_path = os.path.join(tmp_dir, filename)
            save(abs_path, content)
            abs_paths[filename] = abs_path

        self.api.upload_package(package_reference, abs_paths, retry=1, retry_wait=0,
                                no_overwrite=None)

    def _upload_recipe(self, conan_reference, base_files=None, retry=1, retry_wait=0):

        files = hello_source_files(3, [1, 12])
        if base_files:
            files.update(base_files)
        content = """
from conans import ConanFile

class MyConan(ConanFile):
    name = "%s"
    version = "%s"
    settings = arch, compiler, os
""" % (conan_reference.name, conan_reference.version)
        files[CONANFILE] = content
        files_md5s = {filename: md5(content) for filename, content in files.items()}
        conan_digest = FileTreeManifest(123123123, files_md5s)

        tmp_dir = temp_folder()
        abs_paths = {}
        for filename, content in files.items():
            abs_path = os.path.join(tmp_dir, filename)
            save(abs_path, content)
            abs_paths[filename] = abs_path
        abs_paths[CONAN_MANIFEST] = os.path.join(tmp_dir, CONAN_MANIFEST)
        conan_digest.save(tmp_dir)

        self.api.upload_recipe(conan_reference, abs_paths, retry, retry_wait, None, None)
