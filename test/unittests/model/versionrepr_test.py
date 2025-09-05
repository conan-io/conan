import pytest

from conan.internal.model.info import _VersionRepr
from conan.internal.model.version import Version


class TestVersionRepr:

    def test_text(self):
        v1 = Version("master+build2")
        vr = _VersionRepr(v1)
        assert vr.major() == "master.Y.Z"
        assert vr.minor() == "master.0.Z"
        assert vr.patch() == "master.0.0"
        assert vr.pre() == "master.0.0"
        assert vr.build == "build2"
        assert vr.stable() == "master.Y.Z"

    def test_text_cci(self):
        v1 = Version("cci.2025.09.05-alpha1+build2")
        vr = _VersionRepr(v1)
        assert vr.major() == "cci.Y.Z"
        assert vr.minor() == "cci.2025.Z"
        # TODO: Check if this parsed 9 int of 09 is correct
        assert vr.patch() == "cci.2025.9"
        assert vr.pre() == "cci.2025.9-alpha1"
        assert vr.build == "build2"
        assert vr.stable() == "cci.Y.Z"

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
