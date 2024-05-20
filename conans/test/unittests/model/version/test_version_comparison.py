import pytest

from conans.model.version import Version

v = [("1", "2"),
     ("1.0", "1.1"),
     ("1.0.2", "1.1.0"),
     ("1.3", "1.22"),
     ("1.1.3", "1.1.22"),
     ("1.1.1.3", "1.1.1.22"),
     ("1.1.1.1.3", "1.1.1.1.22"),
     # Different lengths
     ("1.0", "2"),
     ("1.2", "1.3.1"),
     ("1.0.2", "1.1"),
     ("1.2.3", "1.11"),
     ("1.2", "1.2.3"),
     ("1.2.2.2", "1.2.3"),
     ("1.2.3", "1.2.3.2"),
     ("4", "4.0.1"),
     ("4", "4.0.0.1"),
     # Now with letters
     ("1.1.a", "1.1.b"),
     ("1.1.1.abc", "1.1.1.abz"),
     ("a.b.c", "b.c"),
     ("1.1", "1.a"),
     ("1.1", "1.1a"),
     ("1.1", "1.1.a"),
     ("1.1.a", "1.2"),
     # Arterisk are before digits
     ("1.1*", "1.20"),
     ("1.1.*", "1.20"),
     ("1.2.2", "1.3.*"),
     ("1.2.2", "1.2.3*"),
     # build is easy
     ("1.1+b1", "1.1+b2"),
     ("1.1", "1.1+b2"),
     ("1.1+b1", "1.2"),
     ("1.1+b.3", "1.1+b.22"),
     # pre-release is challenging
     ("1.1-pre1", "1.1-pre2"),
     ("1.1-alpha.3", "1.1-alpha.22"),
     ("1.1-alpha.3+b1", "1.1-alpha.3+b2"),
     ("1.1-alpha.1", "1.1"),
     ("1.1", "1.2-alpha1"),
     ("1.1-alpha.1", "1.1.0"),  # pre to the generic 1.1 is earlier than 1.1.0
     ("1.0.0-", "1.0.0-alpha1"),
     ("1.2-rc1", "1.2.0"),
     ("1.1.9", "1.2-rc1"),
     # development versions
     ("1.2.1-dev", "1.2.1"),
     ("1.2.1-dev", "1.2.2"),
     ("1.2.1-dev", "1.3"),
     ("1.2.1-dev", "1.3-alpha"),
     ("1.2.0", "1.2.1-dev"),
     ("1.2", "1.2.1-dev"),
     ("1.2-alpha", "1.2.1-dev"),
     ("0.0.1-3", "0.0.1"),
     ("0.0.1-3-1", "0.0.1"),
     ("0.0.1-3-1", "0.0.1-4"),
     ("0.0.1-3", "0.0.1-3-1"),  # 3 is less than 3-1, pure alphanumeric ID "3-1"
     # build + prerelease
     ("1.1-pre.1", "1.1+b.1"),
     ("1.1-pre.1", "1.1-pre.1+b.1"),
     ("1.1-pre.1+b.1", "1.1-pre.1+b.2"),
     ("1.1+b.1", "1.2-pre.1+b.2"),
     ("1.0.0-+2", "1.0.0+2"),  # Note it is not the number, but the prerelease
     ("1.0.0-+2", "1.0.0+1"),  # Even if the build metadata is lower the first one is pre-release
     # cci. schema used in CCI
     ("cci.20230101", "cci.20240101"),
     ]


@pytest.mark.parametrize("v1, v2", v)
def test_comparison(v1, v2):
    v1 = Version(v1)
    v2 = Version(v2)
    assert v1 < v2
    assert v2 > v1
    assert v1 != v2
    assert v1 <= v2
    assert v2 >= v1


def test_build_metadata_is_not_equal():
    # https://github.com/conan-io/conan/issues/5900
    # Shouldn't be an "official" order for build metadata, but as they cannot be equal
    # the order is alphabetic
    assert Version("4.0.0+abc") != Version("4.0.0+xyz")
    assert Version("4.0.0+xyz") != Version("4.0.0+abc")


def test_comparison_with_none():
    assert Version("1.2.3") > None


def test_comparison_with_integer():
    v1 = Version("13.0")
    # Issue: https://github.com/conan-io/conan/issues/12907
    assert v1 > 5
    assert v1 >= 5
    assert v1 < 20
    assert v1 <= 20
    assert v1 == 13
    assert v1 != 14


e = [("1", "1.0"),
     ("1", "1.0.0"),
     ("1.0", "1.0.0"),
     ("1.0", "1.0.0.0"),
     ("1-pre1", "1.0-pre1"),
     ("1-pre1", "1.0.0-pre1"),
     ("1.0-pre1", "1.0.0-pre1"),
     ("1.0-pre1.0", "1.0.0-pre1"),
     ("1-pre1+b1", "1.0-pre1+b1"),
     ("1-pre1+b1", "1.0.0-pre1+b1"),
     ("1.0-pre1+b1", "1.0.0-pre1+b1"),
     ("1+b1", "1.0+b1"),
     ("1+b1", "1.0+b1.0"),
     ("1+b1", "1.0.0+b1"),
     ("1.0+b1", "1.0.0+b1"),
     ("1.2.3", "1.2.3"),
     ]


@pytest.mark.parametrize("v1, v2", e)
def test_equality(v1, v2):
    v1 = Version(v1)
    v2 = Version(v2)
    assert v1 == v2
    assert not v1 != v2
    assert not v1 < v2
    assert not v2 < v1
    assert v1 <= v2
    assert v2 <= v1


def test_elem_comparison():
    v1 = Version("1.2.3b.4-pre.1.2b+build.1.1b")
    major = v1.major
    assert major < 2
    assert major < "2"
    assert major == 1
    assert major != 3
    assert major > 0
    assert str(major) == "1"
    patch = v1.patch
    assert patch < 4
    assert patch > 2
    assert patch < "3c"
    assert patch > "3a"
    assert patch == "3b"
    micro = v1.micro
    assert micro > 3
    assert micro < 5
    assert micro == 4
