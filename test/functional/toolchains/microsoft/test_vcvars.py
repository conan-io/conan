import platform
import textwrap

import pytest

from conan.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
@pytest.mark.tool("visual_studio", "17")
def test_deactivate_vcvars_message():
    client = TestClient()
    conanfile = textwrap.dedent("""
            from conan import ConanFile
            class TestConan(ConanFile):
                generators = "VCVars"
                settings = "os", "compiler", "arch", "build_type"
        """)
    client.save({"conanfile.py": conanfile})
    client.run('install . -s compiler.version=194')
    client.run_command(r'conanbuild.bat')
    assert "[vcvarsall.bat] Environment initialized" in client.out
    client.run_command(r'deactivate_conanvcvars.bat')
    assert "vcvars env cannot be deactivated" in client.out


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows Powershell")
def test_deactivate_vcvars_with_powershell():
    client = TestClient()
    conanfile = textwrap.dedent("""
                from conan import ConanFile
                class TestConan(ConanFile):
                    generators = "VCVars"
                    settings = "os", "compiler", "arch", "build_type"
            """)
    client.save({"conanfile.py": conanfile})
    client.run('install . -c tools.env.virtualenv:powershell=True')
    client.run_command(r'powershell.exe ".\conanbuild.ps1"')
    assert "conanvcvars.ps1: Activated environment" in client.out
    client.run_command(r'powershell.exe ".\deactivate_conanvcvars.ps1"')
    assert "vcvars env cannot be deactivated" in client.out
