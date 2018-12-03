import unittest

from conans.client.graph.range_resolver import _parse_versionexpr
from conans.errors import ConanException


class ParseVersionExprTest(unittest.TestCase):
    def test_backwards_compatibility(self):
        self.assertEqual(_parse_versionexpr("2.3, 3.2"), ("2.3 3.2", True, False))
        self.assertEqual(_parse_versionexpr("2.3, <=3.2"), ("2.3 <=3.2", True, False))

    def test_standard_semver(self):
        self.assertEqual(_parse_versionexpr("*"), ("*", True, False))
        self.assertEqual(_parse_versionexpr(""), ("", True, False))  # Defaults to '*'
        self.assertEqual(_parse_versionexpr("~1"), ("~1", True, False))
        self.assertEqual(_parse_versionexpr("~1.2.3-beta.2"), ("~1.2.3-beta.2", True, False))
        self.assertEqual(_parse_versionexpr("^0.0"), ("^0.0", True, False))
        self.assertEqual(_parse_versionexpr("1.2.3 - 2.3.4"), ("1.2.3 - 2.3.4", True, False))
        self.assertEqual(_parse_versionexpr(">=1.2.3 <1.(2+1).0"),
                         (">=1.2.3 <1.(2+1).0", True, False))

    def test_only_loose(self):
        self.assertEqual(_parse_versionexpr("2.3 ,3.2, loose=True"), ("2.3 3.2", True, False))
        self.assertEqual(_parse_versionexpr("2.3 3.2, loose=False"), ("2.3 3.2", False, False))
        self.assertEqual(_parse_versionexpr("2.3 3.2, loose  = False"), ("2.3 3.2", False, False))
        self.assertEqual(_parse_versionexpr("2.3 3.2,  loose  = True"), ("2.3 3.2", True, False))

    def test_only_prerelease(self):
        self.assertEqual(_parse_versionexpr("2.3, 3.2, include_prerelease=False"),
                         ("2.3 3.2", True, False))
        self.assertEqual(_parse_versionexpr("2.3, 3.2, include_prerelease=True"),
                         ("2.3 3.2", True, True))

    def test_both(self):
        self.assertEqual(_parse_versionexpr("2.3, 3.2, loose=False, include_prerelease=True"),
                         ("2.3 3.2", False, True))
        self.assertEqual(_parse_versionexpr("2.3, 3.2, include_prerelease=True, loose=False"),
                         ("2.3 3.2", False, True))

    def test_invalid(self):
        self.assertRaises(ConanException, _parse_versionexpr, "loose=False, include_prerelease=True")
        self.assertRaises(ConanException, _parse_versionexpr, "2.3, 3.2, unexpected=True")
        self.assertRaises(ConanException, _parse_versionexpr, "2.3, 3.2, loose=Other")
        self.assertRaises(ConanException, _parse_versionexpr, "2.3, 3.2, ")
        self.assertRaises(ConanException, _parse_versionexpr, "2.3, 3.2, 1.2.3")
        self.assertRaises(ConanException, _parse_versionexpr,
                          "2.3 3.2; loose=True, include_prerelease=True")
        self.assertRaises(ConanException, _parse_versionexpr, "loose=True, 2.3 3.3")
