import unittest

from conans.model.info import _VersionRepr
from conans.model.version import Version


class VersionReprTest(unittest.TestCase):

    def test_text(self):
        v1 = Version("master+build2")
        vr = _VersionRepr(v1)
        assert vr.major() == "master"
        assert vr.minor() == "master"
        assert vr.patch() == "master"
        assert vr.pre() == "master"
        assert vr.build == "build2"
        assert vr.stable() == "master"

    def test_patch(self):
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
        v1 = Version("0.2.3-alpha1+build2")
        vr = _VersionRepr(v1)
        self.assertEqual(vr.build, "build2")
        v2 = Version("0.2.3+b178")
        vr = _VersionRepr(v2)
        self.assertEqual(vr.build, "b178")
