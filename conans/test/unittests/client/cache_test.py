# coding=utf-8

import unittest

from six import StringIO

from conans.client.cache import ClientCache
from conans.client.output import ConanOutput
from conans.model.ref import ConanFileReference
from conans.test.utils.test_files import temp_folder
from conans.util.files import mkdir


class CacheTest(unittest.TestCase):

    def test_recipe_exists(self):
        tmp_dir = temp_folder()
        stream = StringIO()
        output = ConanOutput(stream)
        cache = ClientCache(tmp_dir, tmp_dir, output)

        ref = ConanFileReference.loads("lib/1.0@conan/stable")
        self.assertFalse(cache.recipe_exists(ref))

        mkdir(cache.export(ref))
        self.assertTrue(cache.recipe_exists(ref))

        # But if ref has revision and it doesn't match, it doesn't exist
        ref2 = ref.copy_with_rev("revision")
        self.assertFalse(cache.recipe_exists(ref2))

        # Fake the metadata and check again
        with cache.update_metadata(ref) as metadata:
            metadata.recipe.revision = "revision"

        self.assertTrue(cache.recipe_exists(ref2))


