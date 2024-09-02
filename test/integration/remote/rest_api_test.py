import os
import unittest

import pytest
from mock import Mock

from conans import REVISIONS
from conans.client.remote_manager import Remote
from conans.client.rest.auth_manager import ConanApiAuthManager
from conans.client.rest.conan_requester import ConanRequester
from conans.client.rest.rest_client import RestApiClientFactory
from conans.model.conf import ConfDefinition
from conan.test.utils.env import environment_update
from conans.client.userio import UserInput
from conans.model.manifest import FileTreeManifest
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conan.internal.paths import CONANFILE, CONANINFO, CONAN_MANIFEST
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.mocks import LocalDBMock
from conan.test.utils.server_launcher import TestServerLauncher
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import get_free_port
from conans.util.files import md5, save


@pytest.mark.rest_api
class RestApiTest(unittest.TestCase):
    """Open a real server (sockets) to test rest_api function."""

    server = None
    api = None

    @classmethod
    def setUpClass(cls):
        if not cls.server:
            with environment_update({"CONAN_SERVER_PORT": str(get_free_port())}):
                cls.server = TestServerLauncher(server_capabilities=['ImCool', 'TooCool'])
                cls.server.start()

                filename = os.path.join(temp_folder(), "conan.conf")
                save(filename, "")
                config = ConfDefinition()
                requester = ConanRequester(config)
                client_factory = RestApiClientFactory(requester=requester,
                                                      config=config)
                localdb = LocalDBMock()

                mocked_user_input = UserInput(non_interactive=False)
                mocked_user_input.get_username = Mock(return_value="private_user")
                mocked_user_input.get_password = Mock(return_value="private_pass")

                # FIXME: Missing mock
                cls.auth_manager = ConanApiAuthManager(client_factory, temp_folder(), localdb, config)
                cls.remote = Remote("myremote", "http://127.0.0.1:%s" % str(cls.server.port), True,
                                    True)
                cls.auth_manager._authenticate(cls.remote, user="private_user",
                                               password="private_pass")
                cls.api = client_factory.new(cls.remote, localdb.access_token, localdb.refresh_token,
                                             {})

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def tearDown(self):
        RestApiTest.server.clean()

    def test_server_capabilities(self):
        capabilities = self.api.server_capabilities()
        self.assertEqual(capabilities, ["ImCool", "TooCool", REVISIONS])

    def test_get_conan(self):
        # Upload a conans
        ref = RecipeReference.loads("conan1/1.0.0@private_user/testing#myreciperev")
        self._upload_recipe(ref)

        # Get the conans
        tmp_dir = temp_folder()
        self.api.get_recipe(ref, tmp_dir, metadata=None, only_metadata=False)
        self.assertIn(CONANFILE, os.listdir(tmp_dir))
        self.assertIn(CONAN_MANIFEST, os.listdir(tmp_dir))

    def test_get_package(self):
        # Upload a conans
        ref = RecipeReference.loads("conan3/1.0.0@private_user/testing#myreciperev")
        self._upload_recipe(ref)

        # Upload an package
        pref = PkgReference(ref, "1F23223EFDA2", "mypackagerev")
        self._upload_package(pref)

        # Get the package
        tmp_dir = temp_folder()
        self.api.get_package(pref, tmp_dir, metadata=None, only_metadata=False)
        # The hello.cpp file is not downloaded!
        self.assertNotIn("hello.cpp", os.listdir(tmp_dir))

    def test_upload_huge_conan(self):
        ref = RecipeReference.loads("conanhuge/1.0.0@private_user/testing#myreciperev")
        self._upload_recipe(ref, {"file9.cpp": ""})

        tmp = temp_folder()
        files = self.api.get_recipe(ref, tmp, metadata=None, only_metadata=False)
        self.assertIsNotNone(files)
        self.assertFalse(os.path.exists(os.path.join(tmp, "file9.cpp")))

    def test_search(self):
        # Upload a conan1
        conan_name1 = "HelloOnly/0.10@private_user/testing#myreciperev"
        ref1 = RecipeReference.loads(conan_name1)
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
        pref = PkgReference(ref1, "1F23223EFDA", "mypackagerev")
        self._upload_package(pref, {CONANINFO: conan_info})

        # Upload a conan2
        conan_name2 = "helloonlyToo/2.1@private_user/stable#myreciperev"
        ref2 = RecipeReference.loads(conan_name2)
        self._upload_recipe(ref2)

        # Get the info about this ConanFileReference
        info = self.api.search_packages(ref1)
        self.assertEqual(conan_info, info["1F23223EFDA"]["content"])

        # Search packages
        results = self.api.search("HelloOnly*", ignorecase=False)
        results = [RecipeReference(r.name, r.version, r.user, r.channel, revision=None)
                   for r in results]
        ref1.revision = None
        self.assertEqual(results, [ref1])

    def test_remove(self):
        # Upload a conans
        ref = RecipeReference.loads("MyFirstConan/1.0.0@private_user/testing#myreciperev")
        self._upload_recipe(ref)
        ref.revision = "myreciperev"
        path1 = self.server.server_store.base_folder(ref)
        self.assertTrue(os.path.exists(path1))
        # Remove conans and packages
        self.api.remove_recipe(ref)
        self.assertFalse(os.path.exists(path1))

    def test_remove_packages(self):
        ref = RecipeReference.loads("MySecondConan/2.0.0@private_user/testing#myreciperev")
        self._upload_recipe(ref)

        folders = {}
        for sha in ["1", "2", "3", "4", "5"]:
            # Upload an package
            pref = PkgReference(ref, sha, "mypackagerev")
            self._upload_package(pref, {CONANINFO: ""})
            folder = self.server.server_store.package(pref)
            self.assertTrue(os.path.exists(folder))
            folders[sha] = folder

        data = self.api.search_packages(ref)
        self.assertEqual(len(data), 5)

        self.api.remove_packages([PkgReference(ref, "1")])
        self.assertTrue(os.path.exists(self.server.server_store.base_folder(ref)))
        self.assertFalse(os.path.exists(folders["1"]))
        self.assertTrue(os.path.exists(folders["2"]))
        self.assertTrue(os.path.exists(folders["3"]))
        self.assertTrue(os.path.exists(folders["4"]))
        self.assertTrue(os.path.exists(folders["5"]))

        self.api.remove_packages([PkgReference(ref, "2"), PkgReference(ref, "3")])
        self.assertTrue(os.path.exists(self.server.server_store.base_folder(ref)))
        self.assertFalse(os.path.exists(folders["1"]))
        self.assertFalse(os.path.exists(folders["2"]))
        self.assertFalse(os.path.exists(folders["3"]))
        self.assertTrue(os.path.exists(folders["4"]))
        self.assertTrue(os.path.exists(folders["5"]))

        self.api.remove_all_packages(ref)
        self.assertTrue(os.path.exists(self.server.server_store.base_folder(ref)))
        for sha in ["1", "2", "3", "4", "5"]:
            self.assertFalse(os.path.exists(folders[sha]))

    def _upload_package(self, package_reference, base_files=None):

        files = {"conanfile.py": GenConanfile("3").with_requires("1", "12").with_exports("*"),
                 "hello.cpp": "hello",
                 "conanmanifest.txt": ""}
        if base_files:
            files.update(base_files)

        tmp_dir = temp_folder()
        abs_paths = {}
        for filename, content in files.items():
            abs_path = os.path.join(tmp_dir, filename)
            save(abs_path, str(content))
            abs_paths[filename] = abs_path

        self.api.upload_package(package_reference, abs_paths)

    def _upload_recipe(self, ref, base_files=None):

        files = {"conanfile.py": GenConanfile("3").with_requires("1", "12")}
        if base_files:
            files.update(base_files)
        content = """
from conan import ConanFile

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

        self.api.upload_recipe(ref, abs_paths)
