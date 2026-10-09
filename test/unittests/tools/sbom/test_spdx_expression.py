import pytest

from conan.tools.sbom.cyclonedx import _calculate_licenses
from conan.test.utils.mocks import ConanFileMock
from conan.test.utils.mocks import RedirectedTestOutput
from conan.test.utils.tools import redirect_output


@pytest.mark.parametrize(
    "license_value, expected",
    [
        ("MIT", "id"),
        ("mit", "id"),
        ("MIT OR Apache-2.0", "expression"),
        ("( MIT AND ( MIT ) )", "expression"),
        ("(MIT WITH (MIT))", "expression"),
        ("custom license", "name"),
        (("MIT", "Apache-2.0 OR BSD-3-Clause"), "expression"),
    ],
)
def test_license_field(license_value, expected):
    component = type("Component", (), {})()
    component.conanfile = ConanFileMock()
    component.conanfile.license = license_value
    output = RedirectedTestOutput()
    with redirect_output(output):
        entry = _calculate_licenses(component)[0]
        assert "The AND relationship is an assumption" in output
    field = next(iter(entry.get("license", entry)))
    assert field == expected
    if isinstance(license_value, tuple):
        assert entry["expression"] == " AND ".join(f"({lic})" for lic in license_value)
