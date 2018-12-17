import unittest

from conans.client.graph.range_resolver import _parse_versionexpr
from conans.errors import ConanException


class ParseVersionExprTest(unittest.TestCase):
    def test_backwards_compatibility(self):
        output = []
        self.assertEqual(_parse_versionexpr("2.3, 3.2", output), ("2.3 3.2", True, False))
        self.assertTrue(output[0].startswith("WARN: Commas as separator"))
        output = []
        self.assertEqual(_parse_versionexpr("2.3, <=3.2", output), ("2.3 <=3.2", True, False))
        self.assertTrue(output[0].startswith("WARN: Commas as separator"))

    def test_only_spaces_without_warning(self):
        output = []
        self.assertEqual(_parse_versionexpr("2.3 3.2", output), ("2.3 3.2", True, False))
        self.assertEqual(output, [])

    def test_standard_semver(self):
        output = []
        self.assertEqual(_parse_versionexpr("*", output), ("*", True, False))
        self.assertEqual(_parse_versionexpr("", output), ("", True, False))  # Defaults to '*'
        self.assertEqual(_parse_versionexpr("~1", output), ("~1", True, False))
        self.assertEqual(_parse_versionexpr("~1.2.3-beta.2", output), ("~1.2.3-beta.2", True, False))
        self.assertEqual(_parse_versionexpr("^0.0", output), ("^0.0", True, False))
        self.assertEqual(_parse_versionexpr("1.2.3 - 2.3.4", output), ("1.2.3 - 2.3.4", True, False))

    def test_only_loose(self):
        output = []
        self.assertEqual(_parse_versionexpr("2.3 ,3.2, loose=True", output),
                         ("2.3 3.2", True, False))
        self.assertEqual(_parse_versionexpr("2.3 3.2, loose=False", output),
                         ("2.3 3.2", False, False))
        self.assertEqual(_parse_versionexpr("2.3 3.2, loose  = False", output),
                         ("2.3 3.2", False, False))
        self.assertEqual(_parse_versionexpr("2.3 3.2,  loose  = True", output),
                         ("2.3 3.2", True, False))

    def test_only_prerelease(self):
        output = []
        self.assertEqual(_parse_versionexpr("2.3, 3.2, include_prerelease=False", output),
                         ("2.3 3.2", True, False))
        self.assertEqual(_parse_versionexpr("2.3, 3.2, include_prerelease=True", output),
                         ("2.3 3.2", True, True))

    def test_both(self):
        output = []
        self.assertEqual(_parse_versionexpr("2.3, 3.2, loose=False, include_prerelease=True",
                                            output),
                         ("2.3 3.2", False, True))
        self.assertEqual(_parse_versionexpr("2.3, 3.2, include_prerelease=True, loose=False",
                                            output),
                         ("2.3 3.2", False, True))

    def test_invalid(self):
        output = []
        self.assertRaises(ConanException, _parse_versionexpr,
                          "loose=False, include_prerelease=True", output)
        self.assertRaises(ConanException, _parse_versionexpr, "2.3, 3.2, unexpected=True", output)
        self.assertRaises(ConanException, _parse_versionexpr, "2.3, 3.2, loose=Other", output)
        self.assertRaises(ConanException, _parse_versionexpr, "2.3, 3.2, ", output)
        self.assertRaises(ConanException, _parse_versionexpr, "2.3, 3.2, 1.2.3", output)
        self.assertRaises(ConanException, _parse_versionexpr,
                          "2.3 3.2; loose=True, include_prerelease=True", output)
        self.assertRaises(ConanException, _parse_versionexpr, "loose=True, 2.3 3.3", output)
        self.assertRaises(ConanException, _parse_versionexpr,
                          "2.3, 3.2, 1.4, loose=False, include_prerelease=True", output)
        self.assertRaises(ConanException, _parse_versionexpr, ">=1.2.3 <1.(2+1).0", output)
