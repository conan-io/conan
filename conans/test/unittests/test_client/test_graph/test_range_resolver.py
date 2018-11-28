import unittest
from conans.client.graph.range_resolver import _parse_versionexpr
from conans.test.utils.tools import TestBufferConanOutput


class ParseVersionExpr(unittest.TestCase):
    def test_backwards_compatibility(self):
        output = TestBufferConanOutput()
        self.assertEqual(_parse_versionexpr("2.3, 3.2", output), ("2.3 3.2", True, False))
        self.assertEqual(_parse_versionexpr("2.3, <=3.2", output), ("2.3 <=3.2", True, False))

    def test_only_loose(self):
        output = TestBufferConanOutput()
        self.assertEqual(_parse_versionexpr("2.3 ,3.2, loose=True", output), ("2.3 3.2", True, False))
        self.assertEqual(_parse_versionexpr("2.3 3.2, loose=False", output), ("2.3 3.2", False, False))
        self.assertEqual(_parse_versionexpr("2.3 3.2, loose  = False", output), ("2.3 3.2", False, False))
        self.assertEqual(_parse_versionexpr("2.3 3.2,  loose  = True", output), ("2.3 3.2", True, False))

    def test_only_prerelease(self):
        output = TestBufferConanOutput()
        self.assertEqual(_parse_versionexpr("2.3, 3.2, include_prerelease=False", output), ("2.3 3.2", True, False))
        self.assertEqual(_parse_versionexpr("2.3, 3.2, include_prerelease=True", output), ("2.3 3.2", True, True))

    def test_both(self):
        output = TestBufferConanOutput()
        self.assertEqual(_parse_versionexpr("2.3, 3.2, loose=False, include_prerelease=True", output),
                         ("2.3 3.2", False, True))
        self.assertEqual(_parse_versionexpr("2.3, 3.2, include_prerelease=True, loose=False", output),
                         ("2.3 3.2", False, True))

    def test_invalid(self):
        output = TestBufferConanOutput()
        self.assertEqual(_parse_versionexpr("loose=False, include_prerelease=True", output), ("", False, True))
        self.assertEqual(_parse_versionexpr("2.3, 3.2, unexpected=True", output),
                         ("2.3 3.2 unexpected=True", True, False))
        self.assertEqual(_parse_versionexpr("2.3, 3.2, loose=Other", output),
                         ("2.3 3.2 loose=Other", True, False))
        self.assertEqual(_parse_versionexpr("2.3, 3.2, ", output),
                         ("2.3 3.2 ", True, False))
