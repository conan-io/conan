import pytest

from conan.tools.sbom.cyclonedx import _calculate_licenses, _is_valid_spdx_expression, _is_valid_spdx_license
from conan.test.utils.mocks import ConanFileMock


@pytest.mark.parametrize(
    "expression",
    [
        "MIT OR Apache-2.0",
        "MIT AND Apache-2.0",
        "MIT WITH Apache-2.0",
        "( MIT OR Apache-2.0 )",
        "( MIT OR Apache-2.0 ) AND BSD-3-Clause",
        "MIT OR ( Apache-2.0 )",
        "( MIT OR ( MIT ) )",
        "(MIT OR (MIT))",
    ],
)
def test_valid_spdx_expressions(expression):
    assert _is_valid_spdx_expression(expression)


@pytest.mark.parametrize(
    "expression",
    [
        "",
        "custom license",
        "MIT OR custom",
        "MIT AND",
        "OR MIT",
        "MIT OR",
        "( MIT OR Apache-2.0",
        "MIT OR Apache-2.0 )",
    ],
)
def test_invalid_spdx_expressions(expression):
    assert not _is_valid_spdx_expression(expression)


@pytest.mark.parametrize(
    "license_value",
    [
        "MIT",
        "apache-2.0",
        "GPL-2.0-or-later+",
        "LicenseRef-Proprietary",
        "LLVM-exception",
        "LicenseRef-23",
        "LicenseRef-MIT-Style-1",
        "DocumentRef-spdx-tool-1.2:LicenseRef-MIT-Style-2",
    ],
)
def test_valid_spdx_license(license_value):
    assert _is_valid_spdx_license(license_value)


@pytest.mark.parametrize(
    "license_value",
    [
        "custom",
        "LicenseRef-",
        "OR",
    ],
)
def test_invalid_spdx_license(license_value):
    assert not _is_valid_spdx_license(license_value)


@pytest.mark.parametrize(
    "license_value, expected",
    [
        ("MIT", "id"),
        ("mit", "id"),
        ("MIT OR Apache-2.0", "expression"),
        ("( MIT OR ( MIT ) )", "expression"),
        ("(MIT OR (MIT))", "expression"),
        ("custom license", "name"),
    ],
)
def test_license_field(license_value, expected):
    component = type("Component", (), {})()
    component.conanfile = ConanFileMock()
    component.conanfile.license = license_value
    field = next(iter(_calculate_licenses(component)[0]["license"]))
    assert field == expected
