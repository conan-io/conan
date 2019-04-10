# coding=utf-8


import unittest

from conans.client.tools.version import Version
from conans.errors import ConanException


class ToolVersionTests(unittest.TestCase):
    def test_invalid_values(self):
        self.assertRaises(ConanException, Version, "")
        self.assertRaises(ConanException, Version, " ")
        self.assertRaises(ConanException, Version, "\t")
        self.assertRaises(ConanException, Version, "1\t2")
        self.assertRaises(ConanException, Version, "1\n2")
        self.assertRaises(ConanException, Version, "1 2")

        self.assertRaises(ConanException, Version, "a.b.c")
        self.assertRaises(ConanException, Version, "1a.2.3")
        self.assertRaises(ConanException, Version, "1.2.3.a")
        self.assertRaises(ConanException, Version, "1.2.3-a")
        self.assertRaises(ConanException, Version, "1.2.3 a")
        self.assertRaises(ConanException, Version, "a 1.2.3")
        self.assertRaises(ConanException, Version, "1.2.3.4")
        self.assertRaises(ConanException, Version, "1.2.")

        self.assertRaises(ConanException, Version, unittest)

    def test_version_string_3(self):
        v = Version("1.2.3")
        self.assertEqual(v.major, "1")
        self.assertEqual(v.minor, "2")
        self.assertEqual(v.patch, "3")

        v = Version("134.2434.33434")
        self.assertEqual(v.major, "134")
        self.assertEqual(v.minor, "2434")
        self.assertEqual(v.patch, "33434")

    def test_version_string_2(self):
        v = Version("1.2")
        self.assertEqual(v.major, "1")
        self.assertEqual(v.minor, "2")
        self.assertEqual(v.patch, None)

        v = Version("134.2434")
        self.assertEqual(v.major, "134")
        self.assertEqual(v.minor, "2434")
        self.assertEqual(v.patch, None)

    def test_version_string_1(self):
        v = Version("1")
        self.assertEqual(v.major, "1")
        self.assertEqual(v.minor, None)
        self.assertEqual(v.patch, None)

        v = Version("134")
        self.assertEqual(v.major, "134")
        self.assertEqual(v.minor, None)
        self.assertEqual(v.patch, None)

    def test_equality(self):
        self.assertTrue(Version("1.2.3") == "1.2.3")
        self.assertTrue(Version("1.2.3") == Version("1.2.3"))

        self.assertTrue(Version("234") == "234")
        self.assertTrue(Version("234") == Version("234"))

        self.assertTrue(Version("234") == "234")
        self.assertTrue(Version("234") == Version("234"))

        self.assertTrue(Version("1.0.2") == "1.0.2")
        self.assertTrue(Version("1.0.2") == Version("1.0.2"))

        self.assertTrue(Version("0.0.0") == "0")
        self.assertTrue(Version("0.0.0") == Version("0"))

    def test_inequality(self):
        self.assertTrue(Version("1.2.3") != "1.2.4")
        self.assertTrue(Version("1.2.3") != Version("1.2.4"))

        self.assertTrue(Version("1") != "2")
        self.assertTrue(Version("1") != Version("2"))

    def test_gt(self):
        self.assertTrue(Version("1.2") > "1")
        self.assertTrue(Version("1.2") > Version("1"))

        self.assertFalse(Version("1.0") > "1")
        self.assertFalse(Version("1.0.0") > "1")
        self.assertFalse(Version("1") > "1.0")
        self.assertFalse(Version("1") > "1.0.0")

    def test_gte(self):
        self.assertTrue(Version("1.0") >= "1")
        self.assertTrue(Version("1.0.0") >= "1")
        self.assertTrue(Version("1") >= "1.0")
        self.assertTrue(Version("1") >= "1.0.0")
