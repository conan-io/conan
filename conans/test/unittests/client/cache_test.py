# coding=utf-8

import unittest

from six import StringIO

from conans.client.cache import ClientCache
from conans.client.output import ConanOutput
from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.test_files import temp_folder
from conans.util.files import mkdir


class CacheTest(unittest.TestCase):

    def setUp(self):
        tmp_dir = temp_folder()
        stream = StringIO()
        output = ConanOutput(stream)
        self.cache = ClientCache(tmp_dir, tmp_dir, output)
        self.ref = ConanFileReference.loads("lib/1.0@conan/stable")

    def test_recipe_exists(self):

        self.assertFalse(self.cache.recipe_exists(self.ref))

        mkdir(self.cache.export(self.ref))
        self.assertTrue(self.cache.recipe_exists(self.ref))

        # But if ref has revision and it doesn't match, it doesn't exist
        ref2 = self.ref.copy_with_rev("revision")
        self.assertFalse(self.cache.recipe_exists(ref2))

        # Fake the metadata and check again
        with self.cache.package_layout(self.ref).update_metadata() as metadata:
            metadata.recipe.revision = "revision"

        self.assertTrue(self.cache.recipe_exists(ref2))

    def test_package_exists(self):
        pref = PackageReference(self.ref, "999")
        self.assertFalse(self.cache.package_exists(pref))

        mkdir(self.cache.export(self.ref))
        mkdir(self.cache.package(pref))
        self.assertTrue(self.cache.package_exists(pref))

        # But if ref has revision and it doesn't match, it doesn't exist
        ref2 = self.ref.copy_with_rev("revision")
        pref2 = PackageReference(ref2, "999", "prevision")
        self.assertFalse(self.cache.package_exists(pref2))

        # Fake the metadata and check again
        with self.cache.package_layout(self.ref).update_metadata() as metadata:
            metadata.recipe.revision = "revision"
            metadata.packages[pref2.id].revision = "prevision"

        self.assertTrue(self.cache.package_exists(pref2))
