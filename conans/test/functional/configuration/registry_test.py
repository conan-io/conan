import os
import unittest

from conans.client.cache.remote_registry import RemoteRegistry, default_remotes, dump_registry, \
    load_registry_txt, migrate_registry_file, Remote
from conans.errors import ConanException
from conans.model.ref import ConanFileReference
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestBufferConanOutput, TestClient
from conans.util.files import save
from conans.client.cache.cache import ClientCache


class RegistryTest(unittest.TestCase):

    '''def retro_compatibility_test(self):
        f = os.path.join(temp_folder(), "aux_file")
        save(f, """conan.io https://server.conan.io
""")  # Without SSL parameter
        new_path = os.path.join(temp_folder(), "aux_file.json")
        migrate_registry_file(f, new_path)
        cache = ClientCache(os.path.dirname(new_path), None, TestBufferConanOutput())
        registry = RemoteRegistry(cache)
        self.assertEqual(list(registry.load_remotes().values()),
                         [("conan.io", "https://server.conan.io", True)])

    def to_json_migration_test(self):
        tmp = temp_folder()
        conf_dir = os.path.join(tmp, ".conan")
        f = os.path.join(conf_dir, "registry.txt")
        save(f, """conan.io https://server.conan.io True

lib/1.0@conan/stable conan.io
other/1.0@lasote/testing conan.io
""")
        client = TestClient(base_folder=tmp, servers=False)
        registry = client.cache.registry
        self.assertEqual(list(registry.load_remotes().values()),
                         [("conan.io", "https://server.conan.io", True)])
        expected = {'lib/1.0@conan/stable': 'conan.io',
                    'other/1.0@lasote/testing': 'conan.io'}
        self.assertEqual(registry.refs_list, expected)'''

    def add_remove_update_test(self):
        f = os.path.join(temp_folder(), "aux_file")
        save(f, dump_registry(default_remotes, {}, {}))
        cache = ClientCache(os.path.dirname(f), None, TestBufferConanOutput())
        registry = RemoteRegistry(cache)

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
        f = os.path.join(tmp_folder, ".conan", "registry.json")
        save(f, """
{
 "remotes": [
  {
   "url": "https://server.conan.io",
   "verify_ssl": true,
   "name": "conan.io"
  }
 ],
 "references": {}
}
""")
        cache = ClientCache(tmp_folder, None, TestBufferConanOutput())
        registry = RemoteRegistry(cache)
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

    @staticmethod
    def _get_registry():
        f = os.path.join(temp_folder(), "aux_file")
        remotes, refs = load_registry_txt("conan.io https://server.conan.io True\n"
                                          "conan.io2 https://server2.conan.io True\n")
        reg = dump_registry(remotes, refs, {})
        save(f, reg)
        return RemoteRegistry(f)
