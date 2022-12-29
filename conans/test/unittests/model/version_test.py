import unittest

from conans.model.version import Version


class VersionTest(unittest.TestCase):

    def test_simple(self):
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
        self.assertFalse(v1.compatible("1.2.2"))
        v2 = v1.minor()
        self.assertTrue(v2.compatible("1.X"))
        self.assertTrue(v2.compatible("1.2.3.4"))
        self.assertFalse(v2.compatible("1.3.3.4"))
        self.assertTrue(v2.major().compatible("1.3.3.4"))

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

    def test_build_metadata_is_not_equal(self):
        # https://github.com/conan-io/conan/issues/5900
        self.assertNotEqual(Version("4.0.0+abc"), Version("4.0.0+xyz"))
        # Shouldn't be an "official" order for build metadata, but as they cannot be equal
        # the order is alphabetic
        self.assertTrue(Version("4.0.0+abc") > Version("4.0.0+xyz"))
        self.assertTrue(Version("4.0.0+xyz") < Version("4.0.0+abc"))

    def test_text(self):
        v1 = Version("master+build2")
        self.assertEqual(v1.major(), "master")
        self.assertEqual(v1.minor(), "master")
        self.assertEqual(v1.patch(), "master")
        self.assertEqual(v1.pre(), "master")
        self.assertEqual(v1.build, "build2")
        self.assertEqual(v1.stable(), "master")

    def test_patch(self):
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

    def test_build(self):
        v1 = Version("0.2.3-alpha1+build2")
        self.assertEqual(v1.build, "build2")
        v2 = Version("0.2.3+b178")
        self.assertEqual(v2.build, "b178")

    def test_msvc_generic(self):
        v1 = Version("19.1X")
        v2 = Version("19.2X")
        v3 = Version("19.3X")

        assert v1 < v2
        assert v1 < v3
        assert v1 < "19.2X"
        assert v1 < "19.21"
        assert v1 < "19.11"
        assert not v1 > "19.13"
        assert v2 < v3
        assert v2 < "19.37"

