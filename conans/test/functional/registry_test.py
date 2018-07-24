import unittest
import os
from conans.test.utils.test_files import temp_folder
from conans.client.remote_registry import RemoteRegistry
from conans.model.ref import ConanFileReference
from conans.errors import ConanException
from conans.test.utils.tools import TestBufferConanOutput
from conans.util.files import save


class RegistryTest(unittest.TestCase):

    def retro_compatibility_test(self):
        f = os.path.join(temp_folder(), "aux_file")
        save(f, """conan.io https://server.conan.io
""")  # Without SSL parameter
        registry = RemoteRegistry(f, TestBufferConanOutput())
        self.assertEqual(registry.remotes, [("conan.io", "https://server.conan.io", True)])

    def add_remove_update_test(self):
        f = os.path.join(temp_folder(), "aux_file")
        registry = RemoteRegistry(f, TestBufferConanOutput())

        # Add
        registry.add("local", "http://localhost:9300")
        self.assertEqual(registry.remotes, [("conan-center", "https://conan.bintray.com", True),
                                            ("local", "http://localhost:9300", True)])
        # Add
        registry.add("new", "new_url", False)
        self.assertEqual(registry.remotes, [("conan-center", "https://conan.bintray.com", True),
                                            ("local", "http://localhost:9300", True),
                                            ("new", "new_url", False)])
        with self.assertRaises(ConanException):
            registry.add("new", "new_url")
        # Update
        registry.update("new", "other_url")
        self.assertEqual(registry.remotes, [("conan-center", "https://conan.bintray.com", True),
                                            ("local", "http://localhost:9300", True),
                                            ("new", "other_url", True)])
        with self.assertRaises(ConanException):
            registry.update("new2", "new_url")

        registry.update("new", "other_url", False)
        self.assertEqual(registry.remotes, [("conan-center", "https://conan.bintray.com", True),
                                            ("local", "http://localhost:9300", True),
                                            ("new", "other_url", False)])

        # Remove
        registry.remove("local")
        self.assertEqual(registry.remotes, [("conan-center", "https://conan.bintray.com", True),
                                            ("new", "other_url", False)])
        with self.assertRaises(ConanException):
            registry.remove("new2")

    def refs_test(self):
        f = os.path.join(temp_folder(), "aux_file")
        registry = RemoteRegistry(f, TestBufferConanOutput())
        ref = ConanFileReference.loads("MyLib/0.1@lasote/stable")

        remotes = registry.remotes
        registry.set_ref(ref, remotes[0].name)
        remote = registry.get_recipe_remote(ref)
        self.assertEqual(remote, remotes[0])

        registry.set_ref(ref, remotes[0].name)
        remote = registry.get_recipe_remote(ref)
        self.assertEqual(remote, remotes[0])

    def insert_test(self):
        f = os.path.join(temp_folder(), "aux_file")
        save(f, "conan.io https://server.conan.io True")
        registry = RemoteRegistry(f, TestBufferConanOutput())
        registry.add("repo1", "url1", True, insert=0)
        self.assertEqual(registry.remotes, [("repo1", "url1", True),
                                            ("conan.io", "https://server.conan.io", True)])
        registry.add("repo2", "url2", True, insert=1)
        self.assertEqual(registry.remotes, [("repo1", "url1", True),
                                            ("repo2", "url2", True),
                                            ("conan.io", "https://server.conan.io", True)])
        registry.add("repo3", "url3", True, insert=5)
        self.assertEqual(registry.remotes, [("repo1", "url1", True),
                                            ("repo2", "url2", True),
                                            ("conan.io", "https://server.conan.io", True),
                                            ("repo3", "url3", True)])

    @staticmethod
    def _get_registry():
        f = os.path.join(temp_folder(), "aux_file")
        save(f, "conan.io https://server.conan.io True\n"
                "conan.io2 https://server2.conan.io True\n")
        return RemoteRegistry(f, TestBufferConanOutput())

    def revisions_reference_already_exist_test(self):

        registry = self._get_registry()
        ref = ConanFileReference.loads("lib/1.0@user/channel")
        # Test already exists
        registry.add_ref(ref, "conan.io")
        with self.assertRaisesRegexp(ConanException, "already exists"):
            registry.add_ref(ref.copy_with_revision("revision"), "conan.io")

    def revisions_delete_test(self):
        ref = "lib/1.0@user/channel"
        registry = self._get_registry()
        # Test delete without revision
        registry.add_ref(ConanFileReference.loads(ref + "#revision"), "conan.io")
        registry.remove_ref(ConanFileReference.loads(ref))
        self.assertIsNone(registry.get_ref_with_revision(ConanFileReference.loads(ref)))

    def revisions_get_test(self):
        # Test get with revision, only if revision
        ref = ConanFileReference.loads("lib/1.0@user/channel")
        registry = self._get_registry()
        registry.add_ref(ref, "conan.io")
        self.assertEquals(registry.get_ref_with_revision(ref), ref)
        registry.remove_ref(ref)
        ref_with_rev = ref.copy_with_revision("Revision")
        registry.add_ref(ref_with_rev, "conan.io")
        self.assertEquals(registry.get_ref_with_revision(ref), ref_with_rev)
        self.assertEquals(registry.get_ref_with_revision(ref_with_rev), ref_with_rev)
        self.assertNotEquals(registry.get_ref_with_revision(ref.copy_with_revision("OtherRevision")),
                             ref_with_rev)

    def revisions_update_test(self):
        ref = ConanFileReference.loads("lib/1.0@user/channel")
        registry = self._get_registry()
        registry.add_ref(ref.copy_with_revision("revision"), "conan.io")
        registry.update_ref(ref, "conan.io2")
        self.assertEquals(registry.get_recipe_remote(ref).name, "conan.io2")
        self.assertEquals(registry.get_recipe_remote(ref.copy_with_revision("revision")).name,
                          "conan.io2")

        registry.update_ref(ref.copy_with_revision("revision"), "conan.io")
        self.assertEquals(registry.get_recipe_remote(ref).name, "conan.io")
        self.assertEquals(registry.get_recipe_remote(ref.copy_with_revision("revision")).name,
                          "conan.io")
