import os
import tempfile
import unittest

from mock import Mock

from conans.client.client_cache import ClientCache
from conans.client.remote_manager import RemoteManager
from conans.client.remote_registry import Remote
from conans.errors import NotFoundException
from conans.model.ref import ConanFileReference, PackageReference
from conans.model.manifest import FileTreeManifest
from conans.paths import CONAN_MANIFEST, CONANINFO
from conans.test.utils.tools import TestBufferConanOutput, TestClient
from conans.test.utils.test_files import temp_folder
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.util.files import save


class MockRemoteClient(object):

    def __init__(self):
        self.upload_package = Mock()
        self.get_conan_digest = Mock()
        tmp_folder = tempfile.mkdtemp(suffix='conan_download')
        save(os.path.join(tmp_folder, "one.txt"), "ONE")
        self.get_recipe = Mock(return_value={"one.txt": os.path.join(tmp_folder, "one.txt")})

        tmp_folder = tempfile.mkdtemp(suffix='conan_download')
        save(os.path.join(tmp_folder, "one.txt"), "ONE")
        self.get_package = Mock(return_value={"one.txt":  os.path.join(tmp_folder, "one.txt")})
        self.remote_url = None

        self.raise_count = 0

    def upload_conan(self, *argc, **argv):  # @UnusedVariable
        if self.remote_url != "url3":
            self.raise_count += 1
            raise NotFoundException(self.remote_url)
        else:
            return self.remote_url


class RemoteManagerTest(unittest.TestCase):
    """Unit test"""

    def setUp(self):
        self.conan_reference = ConanFileReference.loads("openssl/2.0.3@lasote/testing")
        self.package_reference = PackageReference(self.conan_reference, "123123123")
        self.remote_client = MockRemoteClient()
        self.output = TestBufferConanOutput()
        self.client_cache = ClientCache(temp_folder(), temp_folder(), self.output)
        self.manager = RemoteManager(self.client_cache, self.remote_client, self.output)

    def test_no_remotes(self):
        client = TestClient()
        files = cpp_hello_conan_files("Hello0", "0.1")
        client.save(files)
        client.run("export . lasote/stable")
        client.run("upload Hello0/0.1@lasote/stable", ignore_error=True)
        self.assertIn("ERROR: No default remote defined", client.user_io.out)

    def method_called_test(self):

        save(os.path.join(self.client_cache.package(self.package_reference), CONANINFO), "asdasd")
        manifest = FileTreeManifest.create(self.client_cache.package(self.package_reference))
        save(os.path.join(self.client_cache.package(self.package_reference), CONAN_MANIFEST), str(manifest))

        self.assertFalse(self.remote_client.upload_package.called)
        self.manager.upload_package(self.package_reference, Remote("other", "url", True), 1, 0)
        self.assertTrue(self.remote_client.upload_package.called)

        self.assertFalse(self.remote_client.get_conan_digest.called)
        self.manager.get_conan_digest(self.conan_reference, Remote("other", "url", True))
        self.assertTrue(self.remote_client.get_conan_digest.called)

        self.assertFalse(self.remote_client.get_recipe.called)
        self.manager.get_recipe(self.conan_reference, temp_folder(), Remote("other", "url", True))
        self.assertTrue(self.remote_client.get_recipe.called)

        self.assertFalse(self.remote_client.get_package.called)
        self.manager.get_package(self.package_reference, temp_folder(), Remote("other", "url", True))
        self.assertTrue(self.remote_client.get_package.called)
