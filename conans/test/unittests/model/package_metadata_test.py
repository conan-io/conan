import unittest

from conans.model.package_metadata import PackageMetadata


class PackageMetadataTest(unittest.TestCase):

    def test_load_unload(self):
        a = PackageMetadata()
        a.recipe.revision = "rev"
        a.packages["ID"].recipe_revision = "rec_rev"
        a.packages["ID"].revision = "revp"
        a.packages["ID"].properties["Someprop"] = "23"

        tmp = a.dumps()

        b = PackageMetadata.loads(tmp)

        self.assertEquals(b, a)
        self.assertEqual(b.packages["ID"].properties["Someprop"], "23")

    def test_other_types_than_str(self):
        a = PackageMetadata()
        a.recipe.revision = "rev"
        a.packages["ID"].recipe_revision = 34
        a.packages["ID"].revision = {"23": 45}
        a.packages["ID"].properties["Someprop"] = [23, 2444]

        tmp = a.dumps()

        b = PackageMetadata.loads(tmp)

        self.assertEquals(b, a)
        self.assertEqual(b.packages["ID"].revision, {"23": 45})
        self.assertEqual(b.packages["ID"].properties["Someprop"], [23, 2444])
