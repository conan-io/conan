# coding=utf-8


import unittest

import six

from conans.client.tools.version import Version
from conans.errors import ConanException


class ToolVersionMainComponentsTests(unittest.TestCase):

    def test_invalid_values(self):
        self.assertRaises(ConanException, Version, "")
        self.assertRaises(ConanException, Version, "nonsense")
        self.assertRaises(ConanException, Version, "a1.2.3")

    def test_invalid_message(self):
        with six.assertRaisesRegex(self, ConanException, "Invalid version 'not-valid'"):
            Version("not-valid")

    def test_valid_values(self):
        for v_str in ["1.2.3", "1.2.3-dev90", "1.2.3+dev90", "1.2.3-dev90+more", "1.2.3-dev90+a.b"]:
            v = Version(v_str)
            self.assertEqual(v.major, "1")
            self.assertEqual(v.minor, "2")
            self.assertEqual(v.patch, "3")

    def test_valid_loose(self):
        self.assertTrue(Version.loose)

        # These versions are considered valid with loose validation
        self.assertTrue(Version.loose)
        v = Version("1.2")
        self.assertEqual(v.major, "1")
        self.assertEqual(v.minor, "2")
        self.assertEqual(v.patch, "0")

        v = Version("1")
        self.assertEqual(v.major, "1")
        self.assertEqual(v.minor, "0")
        self.assertEqual(v.patch, "0")

        v = Version(" 1a")
        self.assertEqual(v.major, "1")
        self.assertEqual(v.minor, "0")
        self.assertEqual(v.patch, "0")

    def test_convert_str(self):
        # Check that we are calling the string method
        class A(object):
            def __str__(self):
                return "1.2.3"

        v = Version(A())
        self.assertEqual(v.major, "1")
        self.assertEqual(v.minor, "2")
        self.assertEqual(v.patch, "3")

    def test_compare(self):
        self.assertTrue(Version("1.2.3") == "1.2.3")
        self.assertTrue(Version("1.2.3") == Version("1.2.3"))

        self.assertTrue(Version.loose)
        self.assertTrue(Version("234") == "234")
        self.assertTrue(Version("234") == Version("234"))

    def test_gt(self):
        self.assertTrue(Version("1.2.3") > "1.2.2")

        self.assertTrue(Version.loose)
        self.assertTrue(Version("1.2") > "1")
        self.assertTrue(Version("1.2") > Version("1"))

        self.assertFalse(Version("1.0") > "1")
        self.assertFalse(Version("1.0.0") > "1")
        self.assertFalse(Version("1") > "1.0")
        self.assertFalse(Version("1") > "1.0.0")


class ToolVersionExtraComponentsTests(unittest.TestCase):

    def test_parsing(self):
        v = Version("1.2.3-dev.90.80-dev2+build.b1.b2")
        self.assertEqual(v.prerelease, "dev.90.80-dev2")
        self.assertEqual(v.build, "build.b1.b2")

        v = Version("1.2.305-dev4")
        self.assertEqual(v.prerelease, "dev4")
        self.assertEqual(v.build, "")

        v = Version("1.2.305+dev4")
        self.assertEqual(v.prerelease, "")
        self.assertEqual(v.build, "dev4")

    def test_compare(self):
        # prerelease is taken into account
        self.assertTrue(Version("1.2.3-dev90") != "1.2.3")
        self.assertTrue(Version("1.2.3-dev90") < "1.2.3")
        self.assertTrue(Version("1.2.3-dev90") < Version("1.2.3"))

        # build is not taken into account
        self.assertTrue(Version("1.2") == Version("1.2+dev0"))
        self.assertFalse(Version("1.2") > Version("1.2+dev0"))
        self.assertFalse(Version("1.2") < Version("1.2+dev0"))

        # Unknown release field, not fail (loose=True) and don't affect compare
        self.assertTrue(Version.loose)
        self.assertTrue(Version("1.2.3.4") == Version("1.2.3"))

