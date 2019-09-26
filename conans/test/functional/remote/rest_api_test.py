import os
import platform
import unittest

import requests
from nose.plugins.attrib import attr

from conans import DEFAULT_REVISION_V1
from conans.client.conf import ConanClientConfigParser
from conans.client.rest.conan_requester import ConanRequester
from conans.client.rest.rest_client import RestApiClient
from conans.client.rest.rest_client_v1 import complete_url
from conans.model.info import ConanInfo
from conans.model.manifest import FileTreeManifest
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import CONANFILE, CONANINFO, CONAN_MANIFEST
from conans.test.utils.server_launcher import TestServerLauncher
from conans.test.utils.test_files import hello_source_files, temp_folder
from conans.test.utils.tools import TestBufferConanOutput
from conans.util.env_reader import get_env
from conans.util.files import md5, save


class RestApiUnitTest(unittest.TestCase):

    def relative_url_completion_test(self):

        # test absolute urls
        self.assertEqual(complete_url("http://host2", "http://host"), "http://host")
        self.assertEqual(complete_url("http://host2", "http://host:1234"), "http://host:1234")
        self.assertEqual(complete_url("http://host2", "https://host"), "https://host")
        self.assertEqual(complete_url("http://host2", "https://host:1234"), "https://host:1234")

        # test relative urls
        self.assertEqual(complete_url("http://host", "v1/path_to_file.txt"),
                         "http://host/v1/path_to_file.txt")

        self.assertEqual(complete_url("http://host:1234", "v1/path_to_file.txt"),
                         "http://host:1234/v1/path_to_file.txt")

        self.assertEqual(complete_url("https://host", "v1/path_to_file.txt"),
                         "https://host/v1/path_to_file.txt")

        self.assertEqual(complete_url("https://host:1234", "v1/path_to_file.txt"),
                         "https://host:1234/v1/path_to_file.txt")

        # test relative urls with subdirectory
        self.assertEqual(complete_url("https://host:1234/subdir/", "v1/path_to_file.txt"),
                         "https://host:1234/subdir/v1/path_to_file.txt")


@attr('slow')
@attr('rest_api')
class RestApiTest(unittest.TestCase):
    """Open a real server (sockets) to test rest_api function."""

    server = None
    api = None

    @classmethod
    def setUpClass(cls):
        if not cls.server:
            cls.server = TestServerLauncher(server_capabilities=['ImCool', 'TooCool'])
            cls.server.start()

            filename = os.path.join(temp_folder(), "conan.conf")
            save(filename, "")
            config = ConanClientConfigParser(filename)
            requester = ConanRequester(config, requests)
            cls.api = RestApiClient(TestBufferConanOutput(), requester=requester,
                                    revisions_enabled=False)
            cls.api.remote_url = "http://127.0.0.1:%s" % str(cls.server.port)

            # Authenticate user
            token, _ = cls.api.authenticate("private_user", "private_pass")
            cls.api.token = token

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def tearDown(self):
        RestApiTest.server.clean()

    def server_capabilities_test(self):
        capabilities = self.api.server_capabilities()
        self.assertEqual(capabilities, ["ImCool", "TooCool"])

    def get_conan_test(self):
        # Upload a conans
        ref = ConanFileReference.loads("conan1/1.0.0@private_user/testing")
        self._upload_recipe(ref)

        # Get the conans
        tmp_dir = temp_folder()
        self.api.get_recipe(ref, tmp_dir)
        self.assertIn(CONANFILE, os.listdir(tmp_dir))
        self.assertIn(CONAN_MANIFEST, os.listdir(tmp_dir))

    def get_recipe_manifest_test(self):
        # Upload a conans
        ref = ConanFileReference.loads("conan2/1.0.0@private_user/testing")
        self._upload_recipe(ref)

        # Get the conans digest
        digest = self.api.get_recipe_manifest(ref)
        self.assertEqual(digest.summary_hash, "e925757129f5c49ecb2e8c84ce17e294")
        self.assertEqual(digest.time, 123123123)

    def get_package_test(self):
        # Upload a conans
        ref = ConanFileReference.loads("conan3/1.0.0@private_user/testing")
        self._upload_recipe(ref)

        # Upload an package
        pref = PackageReference(ref, "1F23223EFDA2")
        self._upload_package(pref)

        # Get the package
        tmp_dir = temp_folder()
        self.api.get_package(pref, tmp_dir)
        self.assertIn("hello.cpp", os.listdir(tmp_dir))

    def get_package_info_test(self):
        # Upload a conans
        ref = ConanFileReference.loads("conan3/1.0.0@private_user/testing")
        self._upload_recipe(ref)

        # Upload an package
        pref = PackageReference(ref, "1F23223EFDA")
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
        self._upload_package(pref, {CONANINFO: conan_info})

        # Get the package info
        info = self.api.get_package_info(pref)
        self.assertIsInstance(info, ConanInfo)
        self.assertEqual(info, ConanInfo.loads(conan_info))

    def upload_huge_conan_test(self):
        if platform.system() != "Windows":
            # Upload a conans
            ref = ConanFileReference.loads("conanhuge/1.0.0@private_user/testing")
            files = {"file%s.cpp" % name: "File conent" for name in range(1000)}
            self._upload_recipe(ref, files)

            # Get the conans
            tmp = temp_folder()
            files = self.api.get_recipe(ref, tmp)
            self.assertIsNotNone(files)
            self.assertTrue(os.path.exists(os.path.join(tmp, "file999.cpp")))

    def search_test(self):
        # Upload a conan1
        conan_name1 = "HelloOnly/0.10@private_user/testing"
        ref1 = ConanFileReference.loads(conan_name1)
        self._upload_recipe(ref1)

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
        pref = PackageReference(ref1, "1F23223EFDA")
        self._upload_package(pref, {CONANINFO: conan_info})

        # Upload a conan2
        conan_name2 = "helloonlyToo/2.1@private_user/stable"
        ref2 = ConanFileReference.loads(conan_name2)
        self._upload_recipe(ref2)

        # Get the info about this ConanFileReference
        info = self.api.search_packages(ref1, None)
        self.assertEqual(ConanInfo.loads(conan_info).serialize_min(), info["1F23223EFDA"])

        # Search packages
        results = self.api.search("HelloOnly*", ignorecase=False)
        results = [r.copy_clear_rev() for r in results]
        self.assertEqual(results, [ref1])

    @unittest.skipIf(get_env("TESTING_REVISIONS_ENABLED", False), "Not prepared with revs")
    def remove_test(self):
        # Upload a conans
        ref = ConanFileReference.loads("MyFirstConan/1.0.0@private_user/testing")
        self._upload_recipe(ref)
        ref = ref.copy_with_rev(DEFAULT_REVISION_V1)
        path1 = self.server.server_store.base_folder(ref)
        self.assertTrue(os.path.exists(path1))
        # Remove conans and packages
        self.api.remove_conanfile(ref)
        self.assertFalse(os.path.exists(path1))

    @unittest.skipIf(get_env("TESTING_REVISIONS_ENABLED", False), "Not prepared with revs")
    def remove_packages_test(self):
        ref = ConanFileReference.loads("MySecondConan/2.0.0@private_user/testing#%s"
                                       % DEFAULT_REVISION_V1)
        self._upload_recipe(ref)

        folders = {}
        for sha in ["1", "2", "3", "4", "5"]:
            # Upload an package
            pref = PackageReference(ref, sha, DEFAULT_REVISION_V1)
            self._upload_package(pref)
            folder = self.server.server_store.package(pref)
            self.assertTrue(os.path.exists(folder))
            folders[sha] = folder

        self.api.remove_packages(ref, ["1"])
        self.assertTrue(os.path.exists(self.server.server_store.base_folder(ref)))
        self.assertFalse(os.path.exists(folders["1"]))
        self.assertTrue(os.path.exists(folders["2"]))
        self.assertTrue(os.path.exists(folders["3"]))
        self.assertTrue(os.path.exists(folders["4"]))
        self.assertTrue(os.path.exists(folders["5"]))

        self.api.remove_packages(ref, ["2", "3"])
        self.assertTrue(os.path.exists(self.server.server_store.base_folder(ref)))
        self.assertFalse(os.path.exists(folders["1"]))
        self.assertFalse(os.path.exists(folders["2"]))
        self.assertFalse(os.path.exists(folders["3"]))
        self.assertTrue(os.path.exists(folders["4"]))
        self.assertTrue(os.path.exists(folders["5"]))

        self.api.remove_packages(ref, [])
        self.assertTrue(os.path.exists(self.server.server_store.base_folder(ref)))
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

        self.api.upload_package(package_reference, abs_paths, None, retry=1, retry_wait=0)

    def _upload_recipe(self, ref, base_files=None, retry=1, retry_wait=0):

        files = hello_source_files(3, [1, 12])
        if base_files:
            files.update(base_files)
        content = """
from conans import ConanFile

class MyConan(ConanFile):
    name = "%s"
    version = "%s"
    settings = arch, compiler, os
""" % (ref.name, ref.version)
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

        self.api.upload_recipe(ref, abs_paths, None, retry, retry_wait)
