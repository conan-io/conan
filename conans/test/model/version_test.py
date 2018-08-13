import unittest
from conans.model.version import Version


class VersionTest(unittest.TestCase):

    def simple_test(self):
        v1 = Version("1.2.3")
        self.assertTrue(v1 == "1.2.3")
        self.assertTrue(v1 > "1.1")
        self.assertTrue(v1 > None)
        self.assertTrue(v1 < "1.11")
        self.assertTrue(v1 > "1.2")
        self.assertTrue(v1 > "1.2.2.2")
        self.assertTrue(v1 < "1.2.3.2")
        self.assertEqual(v1.major(), "1.Y.Z")  # 1.X.Y
        self.assertEqual(v1.minor(), "1.2.Z")  # 1.2.Y
        self.assertEqual(v1.patch(), "1.2.3")
        self.assertEqual(v1.pre(), "1.2.3")
        self.assertEqual(v1.build, "")
        self.assertTrue(v1.compatible("1.X"))
        self.assertTrue(v1.compatible("1.2.Y"))
        self.assertFalse(v1.compatible("0.X"))
        v2 = v1.minor()
        self.assertTrue(v2.compatible("1.X"))
        self.assertTrue(v2.compatible("1.2.3.4"))
        self.assertFalse(v2.compatible("1.3.3.4"))

        v1 = Version("1.2.rc1")
        self.assertTrue(v1 < "1.2.0")
        self.assertFalse(v1 < "1.1.9")

        self.assertTrue(Version("1.2.1-dev") < Version("1.2.1"))
        self.assertTrue(Version("1.2.1-dev") < Version("1.2.2"))
        self.assertTrue(Version("1.2.1-dev") < Version("1.3"))
        self.assertTrue(Version("1.2.1-dev") < Version("1.3-alpha"))
        self.assertTrue(Version("1.2.1-dev") > Version("1.2.0"))
        self.assertTrue(Version("1.2.1-dev") > Version("1.2"))
        self.assertTrue(Version("1.2.1-dev") > Version("1.2.alpha"))
        self.assertTrue(Version("1.2.1-dev") > Version("1.2-alpha"))

        self.assertFalse(Version("4") < Version("4.0.0"))
        self.assertFalse(Version("4") > Version("4.0.0"))
        self.assertFalse(Version("4") != Version("4.0.0"))
        self.assertTrue(Version("4") == Version("4.0.0"))
        self.assertTrue(Version("4") <= Version("4.0.0"))
        self.assertTrue(Version("4") >= Version("4.0.0"))
        self.assertTrue(Version("4.0") == Version("4.0.0"))

        self.assertTrue(Version("4.0.0") == Version("4.0.0"))
        self.assertTrue(Version("4.0.1") != "4")
        self.assertFalse(Version("4.0.0.1") == "4")
        self.assertTrue(Version("4.0.0.1") >= "4")

    def text_test(self):
        v1 = Version("master+build2")
        self.assertEqual(v1.major(), "master")
        self.assertEqual(v1.minor(), "master")
        self.assertEqual(v1.patch(), "master")
        self.assertEqual(v1.pre(), "master")
        self.assertEqual(v1.build, "build2")
        self.assertEqual(v1.stable(), "master")

    def patch_test(self):
        v1 = Version("1.2.3-alpha1+build2")
        self.assertEqual(v1.major(), "1.Y.Z")
        self.assertEqual(v1.minor(), "1.2.Z")
        self.assertEqual(v1.patch(), "1.2.3")
        self.assertEqual(v1.pre(), "1.2.3-alpha1")
        self.assertEqual(v1.build, "build2")
        self.assertEqual(v1.stable(), "1.Y.Z")

        v1 = Version("1.2.3+build2")
        self.assertEqual(v1.major(), "1.Y.Z")
        self.assertEqual(v1.minor(), "1.2.Z")
        self.assertEqual(v1.patch(), "1.2.3")
        self.assertEqual(v1.pre(), "1.2.3")
        self.assertEqual(v1.build, "build2")
        self.assertEqual(v1.stable(), "1.Y.Z")

        v1 = Version("0.2.3-alpha1+build2")
        self.assertEqual(v1.major(), "0.Y.Z")
        self.assertEqual(v1.minor(), "0.2.Z")
        self.assertEqual(v1.patch(), "0.2.3")
        self.assertEqual(v1.pre(), "0.2.3-alpha1")
        self.assertEqual(v1.build, "build2")
        self.assertEqual(v1.stable(), "0.2.3-alpha1+build2")

    def build_test(self):
        v1 = Version("0.2.3-alpha1+build2")
        self.assertEqual(v1.build, "build2")
        v2 = Version("0.2.3+b178")
        self.assertEqual(v2.build, "b178")
