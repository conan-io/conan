import os
import textwrap
import unittest

from conans.client.cache.cache import ClientCache
from conans.client.cache.remote_registry import RemoteRegistry, Remote, Remotes,\
    migrate_registry_file
from conans.errors import ConanException
from conans.migrations import CONAN_VERSION
from conans.model.ref import ConanFileReference
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestBufferConanOutput, TestClient
from conans.util.files import save


class RegistryTest(unittest.TestCase):

    def retro_compatibility_test(self):
        folder = temp_folder()
        f = os.path.join(folder, "registry.txt")
        save(f, textwrap.dedent("""conan.io https://server.conan.io

            pkg/0.1@user/testing some_remote
            """))
        output = TestBufferConanOutput()
        cache = ClientCache(folder, output)
        migrate_registry_file(cache, output)
        registry = RemoteRegistry(cache, output)
        self.assertEqual(list(registry.load_remotes().values()),
                         [("conan.io", "https://server.conan.io", True)])

    def to_json_migration_test(self):
        cache_folder = temp_folder()
        f = os.path.join(cache_folder, "registry.txt")
        save(f, """conan.io https://server.conan.io True

lib/1.0@conan/stable conan.io
other/1.0@lasote/testing conan.io
""")
        client = TestClient(cache_folder=cache_folder, servers=False)
        version_file = os.path.join(client.cache_folder, CONAN_VERSION)
        save(version_file, "1.12.0")
        client.run("remote list")
        self.assertIn("conan.io: https://server.conan.io", client.out)
        registry = client.cache.registry
        self.assertEqual(list(registry.load_remotes().values()),
                         [("conan.io", "https://server.conan.io", True)])
        ref1 = ConanFileReference.loads('lib/1.0@conan/stable')
        ref2 = ConanFileReference.loads('other/1.0@lasote/testing')
        expected = {ref1: 'conan.io', ref2: 'conan.io'}

        self.assertEqual(registry.refs_list, expected)

        m = client.cache.package_layout(ref1).load_metadata()
        self.assertEqual(m.recipe.remote, "conan.io")
        m = client.cache.package_layout(ref2).load_metadata()
        self.assertEqual(m.recipe.remote, "conan.io")

    def add_remove_update_test(self):
        f = os.path.join(temp_folder(), "aux_file")
        Remotes().save(f)
        cache = ClientCache(os.path.dirname(f), TestBufferConanOutput())
        registry = cache.registry

        # Add
        registry.add("local", "http://localhost:9300")
        self.assertEqual(list(registry.load_remotes().values()),
                         [("conan-center", "https://conan.bintray.com", True),
                          ("local", "http://localhost:9300", True)])
        # Add
        registry.add("new", "new_url", False)
        self.assertEqual(list(registry.load_remotes().values()),
                         [("conan-center", "https://conan.bintray.com", True),
                          ("local", "http://localhost:9300", True),
                          ("new", "new_url", False)])
        with self.assertRaises(ConanException):
            registry.add("new", "new_url")
        # Update
        registry.update("new", "other_url")
        self.assertEqual(list(registry.load_remotes().values()),
                         [("conan-center", "https://conan.bintray.com", True),
                          ("local", "http://localhost:9300", True),
                          ("new", "other_url", True)])
        with self.assertRaises(ConanException):
            registry.update("new2", "new_url")

        registry.update("new", "other_url", False)
        self.assertEqual(list(registry.load_remotes().values()),
                         [("conan-center", "https://conan.bintray.com", True),
                          ("local", "http://localhost:9300", True),
                          ("new", "other_url", False)])

        # Remove
        registry.remove("local")
        self.assertEqual(list(registry.load_remotes().values()),
                         [("conan-center", "https://conan.bintray.com", True),
                          ("new", "other_url", False)])
        with self.assertRaises(ConanException):
            registry.remove("new2")

    def insert_test(self):
        tmp_folder = temp_folder()
        f = os.path.join(tmp_folder, "remotes.json")
        save(f, """
{
 "remotes": [
  {
   "url": "https://server.conan.io",
   "verify_ssl": true,
   "name": "conan.io"
  }
 ]
}
""")
        output = TestBufferConanOutput()
        cache = ClientCache(tmp_folder, output)
        registry = RemoteRegistry(cache, output)
        registry.add("repo1", "url1", True, insert=0)
        self.assertEqual(list(registry.load_remotes().values()), [Remote("repo1", "url1", True),
                         Remote("conan.io", "https://server.conan.io", True)])
        registry.add("repo2", "url2", True, insert=1)
        self.assertEqual(list(registry.load_remotes().values()), [Remote("repo1", "url1", True),
                         Remote("repo2", "url2", True),
                         Remote("conan.io", "https://server.conan.io", True)])
        registry.add("repo3", "url3", True, insert=5)
        self.assertEqual(list(registry.load_remotes().values()), [Remote("repo1", "url1", True),
                         Remote("repo2", "url2", True),
                         Remote("conan.io", "https://server.conan.io", True),
                         Remote("repo3", "url3", True)])

    def test_remote_none(self):
        """ RemoteRegistry should be able to deal when the URL is None
        """
        f = os.path.join(temp_folder(), "add_none_test")
        Remotes().save(f)
        cache = ClientCache(os.path.dirname(f), TestBufferConanOutput())
        registry = cache.registry

        registry.add("foobar", None)
        self.assertEqual(list(registry.load_remotes().values()),
                         [("conan-center", "https://conan.bintray.com", True),
                          ("foobar", None, True)])
        self.assertIn("WARN: The URL is empty. It must contain scheme and hostname.", cache._output)
        registry.remove("foobar")

        registry.update("conan-center", None)
        self.assertEqual(list(registry.load_remotes().values()),
                         [("conan-center", None, True)])
        self.assertIn("WARN: The URL is empty. It must contain scheme and hostname.", cache._output)
