# coding=utf-8
import copy
import unittest

import pytest

from conans.client.cache.cache import ClientCache
from conans.util.env import environment_update
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.test.utils.test_files import temp_folder
from conans.util.files import mkdir


class CacheTest(unittest.TestCase):

    def setUp(self):
        tmp_dir = temp_folder()
        self.cache = ClientCache(tmp_dir)
        self.ref = RecipeReference.loads("lib/1.0@conan/stable")

    @pytest.mark.xfail(reason="cache2.0")
    def test_recipe_exists(self):
        layout = self.cache.package_layout(self.ref)
        self.assertFalse(layout.recipe_exists())

        mkdir(layout.export())
        self.assertTrue(layout.recipe_exists())

        # But if ref has revision and it doesn't match, it doesn't exist
        with layout.update_metadata() as metadata:
            metadata.clear()

        ref2 = copy.copy(self.ref)
        ref2.revision = "revision"
        layout2 = self.cache.package_layout(ref2)
        self.assertFalse(layout2.recipe_exists())

        # Fake the metadata and check again
        with layout.update_metadata() as metadata:
            metadata.recipe.revision = "revision"

        self.assertTrue(layout2.recipe_exists())

    @pytest.mark.xfail(reason="cache2.0")
    def test_package_exists(self):
        pref = PkgReference(self.ref, "999")
        layout = self.cache.package_layout(self.ref)
        self.assertFalse(layout.package_exists(pref))

        mkdir(layout.export())
        mkdir(layout.package(pref))

        self.assertTrue(layout.package_exists(pref))

        # But if ref has revision and it doesn't match, it doesn't exist
        ref2 = copy.copy(self.ref)
        ref2.revision = "revision"
        pref2 = PkgReference(ref2, "999", "prevision")
        layout2 = self.cache.package_layout(ref2)
        self.assertFalse(layout2.package_exists(pref2))

        # Fake the metadata and check again
        with layout2.update_metadata() as metadata:
            metadata.recipe.revision = "revision"
            metadata.packages[pref2.package_id].revision = "prevision"

        self.assertTrue(layout2.package_exists(pref2))

    def test_localdb_uses_encryption(self):
        localdb = self.cache.localdb
        self.assertIsNone(localdb.encryption_key)

        with environment_update({"CONAN_LOGIN_ENCRYPTION_KEY": "key"}):
            localdb = self.cache.localdb
            self.assertIsNotNone(localdb.encryption_key)
            self.assertEqual(localdb.encryption_key, "key")
