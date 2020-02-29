import unittest

from conans.model.package_metadata import PackageMetadata


class PackageMetadataTest(unittest.TestCase):

    def test_load_unload(self):
        a = PackageMetadata()
        a.recipe.revision = "rev"
        a.recipe.checksums["somefile1"] = {"md5": "50b2137a5d63567b7e88b743a3b594cf",
                                           "sha1": "0b7e8ed59ff4eacb95fd3cc8e17a8034584a96c2"}
        a.packages["ID"].recipe_revision = "rec_rev"
        a.packages["ID"].revision = "revp"
        a.packages["ID"].properties["Someprop"] = "23"
        a.packages["ID"].checksums["somefile2"] = {"md5": "efb7597b146344532fe8da2b79860aaa",
                                                   "sha1": "cc3e6eae41eca26538630f4cd5b0bf4fb52e2d"}

        tmp = a.dumps()

        b = PackageMetadata.loads(tmp)

        self.assertEqual(b, a)
        self.assertEqual(b.packages["ID"].properties["Someprop"], "23")
        self.assertEqual(b.recipe.checksums["somefile1"]["md5"],
                         "50b2137a5d63567b7e88b743a3b594cf")
        self.assertEqual(b.packages["ID"].checksums["somefile2"]["sha1"],
                         "cc3e6eae41eca26538630f4cd5b0bf4fb52e2d")

    def test_other_types_than_str(self):
        a = PackageMetadata()
        a.recipe.revision = "rev"
        a.packages["ID"].recipe_revision = 34
        a.packages["ID"].revision = {"23": 45}
        a.packages["ID"].properties["Someprop"] = [23, 2444]

        tmp = a.dumps()

        b = PackageMetadata.loads(tmp)

        self.assertEqual(b, a)
        self.assertEqual(b.packages["ID"].revision, {"23": 45})
        self.assertEqual(b.packages["ID"].properties["Someprop"], [23, 2444])
