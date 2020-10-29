# coding=utf-8

import os
import unittest

from six import StringIO

from conans.client.cache.cache import ClientCache
from conans.client.output import ConanOutput
from conans.client.tools import environment_append
from conans.model.package_metadata import PackageMetadata
from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.test_files import temp_folder
from conans.util.files import mkdir
from conans.util.files import save


class CacheTest(unittest.TestCase):

    def setUp(self):
        tmp_dir = temp_folder()
        stream = StringIO()
        output = ConanOutput(stream)
        self.cache = ClientCache(tmp_dir, output)
        self.ref = ConanFileReference.loads("lib/1.0@conan/stable")

    def test_recipe_exists(self):
        layout = self.cache.package_layout(self.ref)
        self.assertFalse(layout.recipe_exists())

        mkdir(layout.export())
        self.assertTrue(layout.recipe_exists())

        # But if ref has revision and it doesn't match, it doesn't exist
        with layout.update_metadata() as metadata:
            metadata.clear()

        ref2 = self.ref.copy_with_rev("revision")
        layout2 = self.cache.package_layout(ref2)
        self.assertFalse(layout2.recipe_exists())

        # Fake the metadata and check again
        with layout.update_metadata() as metadata:
            metadata.recipe.revision = "revision"

        self.assertTrue(layout2.recipe_exists())

    def test_package_exists(self):
        pref = PackageReference(self.ref, "999")
        layout = self.cache.package_layout(self.ref)
        self.assertFalse(layout.package_exists(pref))

        mkdir(layout.export())
        mkdir(layout.package(pref))
        save(os.path.join(self.cache.package_layout(self.ref).package_metadata()),
             PackageMetadata().dumps())

        self.assertTrue(layout.package_exists(pref))

        # But if ref has revision and it doesn't match, it doesn't exist
        ref2 = self.ref.copy_with_rev("revision")
        pref2 = PackageReference(ref2, "999", "prevision")
        layout2 = self.cache.package_layout(ref2)
        self.assertFalse(layout2.package_exists(pref2))

        # Fake the metadata and check again
        with layout2.update_metadata() as metadata:
            metadata.recipe.revision = "revision"
            metadata.packages[pref2.id].revision = "prevision"

        self.assertTrue(layout2.package_exists(pref2))

    def test_localdb_uses_encryption(self):
        localdb = self.cache.localdb
        self.assertIsNone(localdb.encryption_key)

        with environment_append({"CONAN_LOGIN_ENCRYPTION_KEY": "key"}):
            localdb = self.cache.localdb
            self.assertIsNotNone(localdb.encryption_key)
            self.assertEqual(localdb.encryption_key, "key")
