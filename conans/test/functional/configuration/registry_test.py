import os
import unittest

from conans.client.remote_registry import RemoteRegistry, default_remotes, dump_registry, \
    load_registry_txt, migrate_registry_file
from conans.errors import ConanException
from conans.model.ref import ConanFileReference
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestBufferConanOutput, TestClient
from conans.util.files import save


class RegistryTest(unittest.TestCase):

    def retro_compatibility_test(self):
        f = os.path.join(temp_folder(), "aux_file")
        save(f, """conan.io https://server.conan.io
""")  # Without SSL parameter
        new_path = os.path.join(temp_folder(), "aux_file.json")
        migrate_registry_file(f, new_path)
        registry = RemoteRegistry(new_path, TestBufferConanOutput())
        self.assertEqual(registry.remotes.list, [("conan.io", "https://server.conan.io", True)])

    def to_json_migration_test(self):
        tmp = temp_folder()
        conf_dir = os.path.join(tmp, ".conan")
        f = os.path.join(conf_dir, "registry.txt")
        save(f, """conan.io https://server.conan.io True

lib/1.0@conan/stable conan.io
other/1.0@lasote/testing conan.io        
""")
        client = TestClient(base_folder=tmp, servers=False)
        registry = client.client_cache.registry
        self.assertEqual(registry.remotes.list, [("conan.io", "https://server.conan.io", True)])
        expected = {'lib/1.0@conan/stable': 'conan.io',
                    'other/1.0@lasote/testing': 'conan.io'}
        self.assertEqual(registry.refs.list, expected)

    def add_remove_update_test(self):
        f = os.path.join(temp_folder(), "aux_file")
        save(f, dump_registry(default_remotes, {}, {}))
        registry = RemoteRegistry(f, TestBufferConanOutput())

        # Add
        registry.remotes.add("local", "http://localhost:9300")
        self.assertEqual(registry.remotes.list,
                         [("conan-center", "https://conan.bintray.com", True),
                          ("local", "http://localhost:9300", True)])
        # Add
        registry.remotes.add("new", "new_url", False)
        self.assertEqual(registry.remotes.list,
                         [("conan-center", "https://conan.bintray.com", True),
                          ("local", "http://localhost:9300", True),
                          ("new", "new_url", False)])
        with self.assertRaises(ConanException):
            registry.remotes.add("new", "new_url")
        # Update
        registry.remotes.update("new", "other_url")
        self.assertEqual(registry.remotes.list,
                         [("conan-center", "https://conan.bintray.com", True),
                          ("local", "http://localhost:9300", True),
                          ("new", "other_url", True)])
        with self.assertRaises(ConanException):
            registry.remotes.update("new2", "new_url")

        registry.remotes.update("new", "other_url", False)
        self.assertEqual(registry.remotes.list,
                         [("conan-center", "https://conan.bintray.com", True),
                          ("local", "http://localhost:9300", True),
                          ("new", "other_url", False)])

        # Remove
        registry.remotes.remove("local")
        self.assertEqual(registry.remotes.list,
                         [("conan-center", "https://conan.bintray.com", True),
                          ("new", "other_url", False)])
        with self.assertRaises(ConanException):
            registry.remotes.remove("new2")

    def refs_test(self):
        f = os.path.join(temp_folder(), "aux_file")
        save(f, dump_registry(default_remotes, {}, {}))
        registry = RemoteRegistry(f, TestBufferConanOutput())
        ref = ConanFileReference.loads("MyLib/0.1@lasote/stable")

        remotes = registry.remotes.list
        registry.refs.set(ref, remotes[0].name)
        remote = registry.refs.get(ref)
        self.assertEqual(remote, remotes[0])

        registry.refs.set(ref, remotes[0].name)
        remote = registry.refs.get(ref)
        self.assertEqual(remote, remotes[0])

    def insert_test(self):
        f = os.path.join(temp_folder(), "aux_file")
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
        registry = RemoteRegistry(f, TestBufferConanOutput())
        registry.remotes.add("repo1", "url1", True, insert=0)
        self.assertEqual(registry.remotes.list, [("repo1", "url1", True),
                         ("conan.io", "https://server.conan.io", True)])
        registry.remotes.add("repo2", "url2", True, insert=1)
        self.assertEqual(registry.remotes.list, [("repo1", "url1", True),
                         ("repo2", "url2", True),
                         ("conan.io", "https://server.conan.io", True)])
        registry.remotes.add("repo3", "url3", True, insert=5)
        self.assertEqual(registry.remotes.list, [("repo1", "url1", True),
                         ("repo2", "url2", True),
                         ("conan.io", "https://server.conan.io", True),
                         ("repo3", "url3", True)])

    @staticmethod
    def _get_registry():
        f = os.path.join(temp_folder(), "aux_file")
        remotes, refs = load_registry_txt("conan.io https://server.conan.io True\n"
                                          "conan.io2 https://server2.conan.io True\n")
        reg = dump_registry(remotes, refs, {})
        save(f, reg)
        return RemoteRegistry(f, TestBufferConanOutput())

    def revisions_reference_already_exist_test(self):

        registry = self._get_registry()
        ref = ConanFileReference.loads("lib/1.0@user/channel")
        # Test already exists
        registry.refs.set(ref, "conan.io", check_exists=True)
        with self.assertRaisesRegexp(ConanException, "already exists"):
            registry.refs.set(ref.copy_with_rev("revision"), "conan.io", check_exists=True)
