import unittest

from conans.model.info import _VersionRepr
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
        self.assertEqual(v1.major, "1")  # 1.X.Y
        self.assertEqual(v1.minor, "2")  # 1.2.Y
        self.assertEqual(v1.patch, "3")
        self.assertEqual(v1.pre, None)
        self.assertEqual(v1.build, None)

        v1 = Version("1.2-rc1")
        self.assertTrue(v1 < "1.2.0")
        self.assertFalse(v1 < "1.1.9")

        self.assertTrue(Version("1.2.1-dev") < Version("1.2.1"))
        self.assertTrue(Version("1.2.1-dev") < Version("1.2.2"))
        self.assertTrue(Version("1.2.1-dev") < Version("1.3"))
        self.assertTrue(Version("1.2.1-dev") < Version("1.3-alpha"))
        self.assertTrue(Version("1.2.1-dev") > Version("1.2.0"))
        self.assertTrue(Version("1.2.1-dev") > Version("1.2"))
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
        self.assertTrue(Version("4.0.0+abc") != Version("4.0.0+xyz"))
        self.assertTrue(Version("4.0.0+xyz") != Version("4.0.0+abc"))

    def test_text(self):
        from conans.model.recipe_ref import Version
        v1 = Version("master+build2")
        vr = _VersionRepr(v1)
        assert vr.major() == "master"
        assert vr.minor() == "master"
        assert vr.patch() == "master"
        assert vr.pre() == "master"
        assert vr.build == "build2"
        assert vr.stable() == "master"

    def test_patch(self):
        from conans.model.recipe_ref import Version
        v1 = Version("1.2.3-alpha1+build2")
        vr = _VersionRepr(v1)
        assert vr.major() == "1.Y.Z"
        assert vr.minor() == "1.2.Z"
        assert vr.patch() == "1.2.3"
        assert vr.pre() == "1.2.3-alpha1"
        assert vr.build == "build2"
        assert vr.stable() == "1.Y.Z"

        v1 = Version("1.2.3+build2")
        vr = _VersionRepr(v1)
        self.assertEqual(vr.major(), "1.Y.Z")
        self.assertEqual(vr.minor(), "1.2.Z")
        self.assertEqual(vr.patch(), "1.2.3")
        self.assertEqual(vr.pre(), "1.2.3")
        self.assertEqual(vr.build, "build2")
        self.assertEqual(vr.stable(), "1.Y.Z")

        v1 = Version("0.2.3-alpha1+build2")
        vr = _VersionRepr(v1)
        self.assertEqual(vr.major(), "0.Y.Z")
        self.assertEqual(vr.minor(), "0.2.Z")
        self.assertEqual(vr.patch(), "0.2.3")
        self.assertEqual(vr.pre(), "0.2.3-alpha1")
        self.assertEqual(vr.build, "build2")
        self.assertEqual(vr.stable(), "0.2.3-alpha1+build2")

        v1 = Version("+build2")
        vr = _VersionRepr(v1)
        assert vr.major() == ""

    def test_build(self):
        from conans.model.recipe_ref import Version
        v1 = Version("0.2.3-alpha1+build2")
        vr = _VersionRepr(v1)
        self.assertEqual(vr.build, "build2")
        v2 = Version("0.2.3+b178")
        vr = _VersionRepr(v2)
        self.assertEqual(vr.build, "b178")
