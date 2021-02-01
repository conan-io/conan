import unittest

from conans.client.graph.range_resolver import satisfying
from conans.errors import ConanException
from conans.test.utils.mocks import TestBufferConanOutput


class BasicMaxVersionTest(unittest.TestCase):
    def test_prereleases_versions(self):
        output = TestBufferConanOutput()
        result = satisfying(["1.1.1", "1.1.11", "1.1.21", "1.1.111"], "", output)
        self.assertEqual(result, "1.1.111")
        # prereleases are ordered
        result = satisfying(["1.1.1-a.1", "1.1.1-a.11", "1.1.1-a.111", "1.1.1-a.21"], "~1.1.1-a",
                            output)
        self.assertEqual(result, "1.1.1-a.111")
        result = satisfying(["1.1.1", "1.1.1-11", "1.1.1-111", "1.1.1-21"], "", output)
        self.assertEqual(result, "1.1.1")
        result = satisfying(["4.2.2", "4.2.3-pre"], "~4.2.3-", output)
        self.assertEqual(result, "4.2.3-pre")
        result = satisfying(["4.2.2", "4.2.3-pre", "4.2.4"], "~4.2.3-", output)
        self.assertEqual(result, "4.2.4")
        result = satisfying(["4.2.2", "4.2.3-pre", "4.2.3"], "~4.2.3-", output)
        self.assertEqual(result, "4.2.3")

    def test_loose_versions(self):
        output = []
        result = satisfying(["4.2.2", "4.2.3-pre"], "~4.2.1,loose=False", output)
        self.assertEqual(result, "4.2.2")
        result = satisfying(["1.1.1", "1.1.2", "1.2", "1.2.1", "1.3", "2.1"], "1.8||1.3,loose=False",
                            output)
        self.assertEqual(result, None)
        result = satisfying(["1.1.1", "1.1.2", "1.2", "1.2.1", "1.3", "2.1"],
                            "1.8||1.3, loose = False ", output)
        self.assertEqual(result, None)
        result = satisfying(["1.1.1", "1.1.2", "1.2", "1.2.1", "1.3", "2.1"], "1.8||1.3", output)
        self.assertEqual(result, "1.3")

    def test_include_prerelease_versions(self):
        output = TestBufferConanOutput()
        result = satisfying(["4.2.2", "4.2.3-pre"], "~4.2.1,include_prerelease = True", output)
        self.assertEqual(result, "4.2.3-pre")
        result = satisfying(["4.2.2", "4.2.3-pre"], "~4.2.1", output)
        self.assertEqual(result, "4.2.2")
        # https://github.com/conan-io/conan/issues/7343
        result = satisfying(["1.0.0-pre"], "~1.0, include_prerelease=True", output)
        self.assertIsNone(result)
        result = satisfying(["1.2.0-pre"], "~1.0, include_prerelease=True", output)
        self.assertIsNone(result)
        # this matches, because it is equivalent to 1.0.X
        result = satisfying(["1.1.0-pre"], "~1.0, include_prerelease=True", output)
        self.assertEqual(result, "1.1.0-pre")
        result = satisfying(["1.0.0-pre"], "<1.0, include_prerelease=True", output)
        self.assertEqual(result, "1.0.0-pre")
        result = satisfying(["1.0.1-pre"], "~1.0, include_prerelease=True", output)
        self.assertEqual(result, "1.0.1-pre")

    def test_basic(self):
        output = []
        result = satisfying(["1.1", "1.2", "1.3", "2.1"], "", output)
        self.assertEqual(result, "2.1")
        result = satisfying(["1.1", "1.2", "1.3", "2.1"], "1", output)
        self.assertEqual(result, "1.3")
        result = satisfying(["1.1", "1.2", "1.3", "2.1"], "1.1", output)
        self.assertEqual(result, "1.1")
        result = satisfying(["1.1", "1.2", "1.3", "2.1"], ">1.1", output)
        self.assertEqual(result, "2.1")
        result = satisfying(["1.1", "1.2", "1.3", "2.1"], "<1.3", output)
        self.assertEqual(result, "1.2")
        result = satisfying(["1.1", "1.2", "1.3", "2.1"], "<=1.3", output)
        self.assertEqual(result, "1.3")
        result = satisfying(["1.1", "1.2", "1.3", "2.1"], ">1.1,<2.1", output)
        self.assertEqual(result, "1.3")
        result = satisfying(["1.1.1", "1.1.2", "1.2.1", "1.3", "2.1"], "<1.2", output)
        self.assertEqual(result, "1.1.2")
        result = satisfying(["1.1.1", "1.1.2", "1.2.1", "1.3", "2.1"], "<1.2.1", output)
        self.assertEqual(result, "1.1.2")
        result = satisfying(["1.1.1", "1.1.2", "1.2.1", "1.3", "2.1"], "<=1.2.1", output)
        self.assertEqual(result, "1.2.1")
        result = satisfying(["1.6.1"], ">1.5.0,<1.6.8", output)
        self.assertEqual(result, "1.6.1")
        result = satisfying(["1.1.1", "1.1.2", "1.2", "1.2.1", "1.3", "2.1"], "<=1.2", output)
        self.assertEqual(result, "1.2.1")
        result = satisfying(["1.1.1", "1.1.2", "1.2", "1.2.1", "1.3", "2.1"], "<1.3", output)
        self.assertEqual(result, "1.2.1")
        result = satisfying(["1.a.1", "master", "X.2", "1.2.1", "1.3", "2.1"], "1.3", output)
        self.assertIn("Version 'master' is not semver", "".join(output))
        self.assertEqual(result, "1.3")
        result = satisfying(["1.1.1", "1.1.2", "1.2", "1.2.1", "1.3", "2.1"], "1.8||1.3", output)
        self.assertEqual(result, "1.3")

        result = satisfying(["1.3", "1.3.1"], "<1.3", output)
        self.assertEqual(result, None)
        result = satisfying(["1.3.0", "1.3.1"], "<1.3", output)
        self.assertEqual(result, None)
        result = satisfying(["1.3", "1.3.1"], "<=1.3", output)
        self.assertEqual(result, "1.3.1")
        result = satisfying(["1.3.0", "1.3.1"], "<=1.3", output)
        self.assertEqual(result, "1.3.1")
        # >2 means >=3.0.0-0
        result = satisfying(["2.1"], ">2", output)
        self.assertEqual(result, None)
        result = satisfying(["2.1"], ">2.0", output)
        self.assertEqual(result, "2.1")
        # >2.1 means >=2.2.0-0
        result = satisfying(["2.1.1"], ">2.1", output)
        self.assertEqual(result, None)
        result = satisfying(["2.1.1"], ">2.1.0", output)
        self.assertEqual(result, "2.1.1")

        # Invalid ranges
        with self.assertRaises(ConanException):
            satisfying(["2.1.1"], "2.3 3.2; include_prerelease=True, loose=False", output)
        with self.assertRaises(ConanException):
            satisfying(["2.1.1"], "2.3 3.2, include_prerelease=Ture, loose=False", output)
        with self.assertRaises(ConanException):
            satisfying(["2.1.1"], "~2.3, abc, loose=False", output)
