import pytest

from conan.tools.sbom.cyclonedx import _calculate_licenses
from conan.test.utils.mocks import ConanFileMock


@pytest.mark.parametrize(
    "license_value, expected",
    [
        ("MIT", "id"),
        ("mit", "id"),
        ("MIT OR Apache-2.0", "expression"),
        ("( MIT AND ( MIT ) )", "expression"),
        ("(MIT WITH (MIT))", "expression"),
        ("custom license", "name"),
    ],
)
def test_license_field(license_value, expected):
    component = type("Component", (), {})()
    component.conanfile = ConanFileMock()
    component.conanfile.license = license_value
    field = next(iter(_calculate_licenses(component)[0]["license"]))
    assert field == expected
