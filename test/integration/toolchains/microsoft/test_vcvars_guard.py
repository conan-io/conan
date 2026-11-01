"""
Test for GitHub issue #19423:
conanvcvars.bat should activate only once, since it can't be deactivated.
The fix adds a VSCMD_VER guard so repeated calls to conanbuild.bat don't
keep appending vcvars paths to %PATH%.
"""
import os
import textwrap

import pytest

from conan.test.utils.tools import TestClient


@pytest.mark.skipif(not (os.name == "nt"), reason="Windows-only test")
def test_vcvars_guard_in_generated_bat():
    """
    The generated conanvcvars.bat must contain an 'if defined VSCMD_VER' guard
    so that vcvarsall.bat is only called once, preventing PATH accumulation.
    Regression test for https://github.com/conan-io/conan/issues/19423
    """
    client = TestClient(path_with_spaces=False)
    client.save({"conanfile.txt": "[generators]\nVCVars"})
    client.run(
        'install . -s os=Windows -s compiler=msvc -s compiler.version=193 '
        '-s compiler.runtime=dynamic '
        '-c tools.microsoft.msbuild:installation_path=C:/'  # fake path, avoids vswhere lookup
    )

    bat_content = client.load("conanvcvars.bat")

    # The guard must be present
    assert "if defined VSCMD_VER" in bat_content, (
        "conanvcvars.bat must guard against re-activation using 'if defined VSCMD_VER'"
    )
    assert "goto :eof" in bat_content, (
        "conanvcvars.bat must skip activation with 'goto :eof' when VS env is already active"
    )
    assert "already active, skipping activation" in bat_content, (
        "conanvcvars.bat must print a message when skipping re-activation"
    )

    # The actual vcvars call must still be present (for first-time activation)
    assert "vcvarsall.bat" in bat_content, (
        "conanvcvars.bat must still call vcvarsall.bat for first activation"
    )


@pytest.mark.skipif(not (os.name == "nt"), reason="Windows-only test")
def test_vcvars_guard_order_correct():
    """
    The guard must come BEFORE the vcvarsall.bat call in conanvcvars.bat.
    """
    client = TestClient(path_with_spaces=False)
    client.save({"conanfile.txt": "[generators]\nVCVars"})
    client.run(
        'install . -s os=Windows -s compiler=msvc -s compiler.version=193 '
        '-s compiler.runtime=dynamic '
        '-c tools.microsoft.msbuild:installation_path=C:/'
    )

    bat_content = client.load("conanvcvars.bat")

    guard_pos = bat_content.find("if defined VSCMD_VER")
    vcvars_pos = bat_content.find("vcvarsall.bat")

    assert guard_pos != -1, "Guard 'if defined VSCMD_VER' not found in conanvcvars.bat"
    assert vcvars_pos != -1, "vcvarsall.bat call not found in conanvcvars.bat"
    assert guard_pos < vcvars_pos, (
        "The VSCMD_VER guard must appear BEFORE the vcvarsall.bat call"
    )


@pytest.mark.skipif(not (os.name == "nt"), reason="Windows-only test")
def test_vcvars_powershell_guard_in_generated_ps1():
    """
    The generated conanvcvars.ps1 must also guard against re-activation
    using $env:VSCMD_VER.
    """
    client = TestClient(path_with_spaces=False)
    client.save({"conanfile.txt": "[generators]\nVCVars"})
    client.run(
        'install . -s os=Windows -s compiler=msvc -s compiler.version=193 '
        '-s compiler.runtime=dynamic '
        '-c tools.microsoft.msbuild:installation_path=C:/ '
        '-c tools.env.virtualenv:powershell=True'
    )

    ps1_content = client.load("conanvcvars.ps1")

    assert "$env:VSCMD_VER" in ps1_content, (
        "conanvcvars.ps1 must guard against re-activation using '$env:VSCMD_VER'"
    )
    assert "already active, skipping activation" in ps1_content, (
        "conanvcvars.ps1 must print a message when skipping re-activation"
    )
