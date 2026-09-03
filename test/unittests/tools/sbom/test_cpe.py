import pytest

from conan.api.model import RecipeReference
from conan.errors import ConanException
from conan.test.utils.mocks import ConanFileMock
from conan.tools.sbom.cyclonedx import _calculate_cpe, _cpe_field, _normalize_cpe


@pytest.mark.parametrize(
    "cpe, version, expected",
    [
        ("cpe:2.3:a:openssl:openssl:*:*:*:*:*:*:*:*", "3.0.5",
         "cpe:2.3:a:openssl:openssl:3.0.5:*:*:*:*:*:*:*"),
        ("cpe:2.3:a:openssl:openssl:1.0.0:*:*:*:*:*:*:*", "3.0.5",
         "cpe:2.3:a:openssl:openssl:1.0.0:*:*:*:*:*:*:*"),
        ("cpe:2.3:a:vendor:product:*:*:*:*:*:*:*:*", "1.2.3+build",
         "cpe:2.3:a:vendor:product:1.2.3\\+build:*:*:*:*:*:*:*"),
        ("cpe:/a:openssl:openssl:3.0.5", "3.0.5", "cpe:/a:openssl:openssl:3.0.5"),
    ],
)
def test_normalize_cpe(cpe, version, expected):
    assert _normalize_cpe(cpe, version, "openssl/3.0.5") == expected


@pytest.mark.parametrize(
    "cpe, error",
    [
        ("bogus", "must start with 'cpe:2.3:' or 'cpe:/'"),
        ("cpe:2.3:a:vendor:product", "must have 13 colon-separated components"),
        ("cpe:2.3:a:vendor:product:1:2:3:4:5:6:7:8:9:10", "must have 13 colon-separated components"),
    ],
)
def test_normalize_cpe_invalid_string(cpe, error):
    with pytest.raises(ConanException, match=error):
        _normalize_cpe(cpe, "1.0", "pkg/1.0")


def test_normalize_cpe_invalid_type():
    with pytest.raises(ConanException, match="expected a string"):
        _normalize_cpe(123, "1.0", "pkg/1.0")


def test_calculate_cpe_from_recipe_attribute():
    ref = RecipeReference.loads("openssl/3.0.5")
    conanfile = ConanFileMock()
    conanfile.cpe = "cpe:2.3:a:openssl:openssl:*:*:*:*:*:*:*:*"
    assert _calculate_cpe(ref, conanfile, None) == \
        "cpe:2.3:a:openssl:openssl:3.0.5:*:*:*:*:*:*:*"


def test_calculate_cpe_no_attribute_no_override():
    ref = RecipeReference.loads("openssl/3.0.5")
    conanfile = ConanFileMock()
    assert _calculate_cpe(ref, conanfile, None) is None


def test_calculate_cpe_override_takes_precedence():
    ref = RecipeReference.loads("openssl/3.0.5")
    conanfile = ConanFileMock()
    conanfile.cpe = "cpe:2.3:a:wrong:wrong:*:*:*:*:*:*:*:*"
    cpes = {"openssl/*": "cpe:2.3:a:openssl:openssl:*:*:*:*:*:*:*:*"}
    assert _calculate_cpe(ref, conanfile, cpes) == \
        "cpe:2.3:a:openssl:openssl:3.0.5:*:*:*:*:*:*:*"


def test_calculate_cpe_override_none_suppresses_recipe_attribute():
    ref = RecipeReference.loads("fmt/10.0")
    conanfile = ConanFileMock()
    conanfile.cpe = "cpe:2.3:a:some:guess:*:*:*:*:*:*:*:*"
    cpes = {"fmt/*": None}
    assert _calculate_cpe(ref, conanfile, cpes) is None


def test_calculate_cpe_override_no_match_falls_back_to_recipe_attribute():
    ref = RecipeReference.loads("openssl/3.0.5")
    conanfile = ConanFileMock()
    conanfile.cpe = "cpe:2.3:a:openssl:openssl:*:*:*:*:*:*:*:*"
    cpes = {"zlib/*": "cpe:2.3:a:zlib:zlib:*:*:*:*:*:*:*:*"}
    assert _calculate_cpe(ref, conanfile, cpes) == \
        "cpe:2.3:a:openssl:openssl:3.0.5:*:*:*:*:*:*:*"


def test_cpe_field_empty_when_no_cpe():
    ref = RecipeReference.loads("openssl/3.0.5")
    conanfile = ConanFileMock()
    assert _cpe_field(ref, conanfile, None) == {}


def test_cpe_field_with_cpe():
    ref = RecipeReference.loads("openssl/3.0.5")
    conanfile = ConanFileMock()
    conanfile.cpe = "cpe:2.3:a:openssl:openssl:*:*:*:*:*:*:*:*"
    assert _cpe_field(ref, conanfile, None) == \
        {"cpe": "cpe:2.3:a:openssl:openssl:3.0.5:*:*:*:*:*:*:*"}
