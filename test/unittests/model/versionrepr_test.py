import pytest

from conan.internal.model.info import _VersionRepr
from conan.internal.model.version import Version


class TestVersionRepr:

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
        assert vr.major() == "1.Y.Z"
        assert vr.minor() == "1.2.Z"
        assert vr.patch() == "1.2.3"
        assert vr.pre() == "1.2.3"
        assert vr.build == "build2"
        assert vr.stable() == "1.Y.Z"

        v1 = Version("0.2.3-alpha1+build2")
        vr = _VersionRepr(v1)
        assert vr.major() == "0.Y.Z"
        assert vr.minor() == "0.2.Z"
        assert vr.patch() == "0.2.3"
        assert vr.pre() == "0.2.3-alpha1"
        assert vr.build == "build2"
        assert vr.stable() == "0.2.3-alpha1+build2"

        v1 = Version("+build2")
        vr = _VersionRepr(v1)
        assert vr.major() == ""

    def test_build(self):
        v1 = Version("0.2.3-alpha1+build2")
        vr = _VersionRepr(v1)
        assert vr.build == "build2"
        v2 = Version("0.2.3+b178")
        vr = _VersionRepr(v2)
        assert vr.build == "b178"
