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


@pytest.mark.tool("visual_studio", "17")
@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
def test_vcvars_winsdk_version():
    client = TestClient(path_with_spaces=False)
    client.save({"conanfile.txt": "[generators]\nVCVars"})
    client.run('install . -s os=Windows -s compiler=msvc -s compiler.version=193 '
               '-s compiler.cppstd=14 -s compiler.runtime=static '
               '-c tools.microsoft:winsdk_version=10.0')

    vcvars = client.load("conanvcvars.bat")
    assert 'vcvarsall.bat"  amd64 10.0 -vcvars_ver=14.3' in vcvars


@pytest.mark.tool("visual_studio", "17")
@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
def test_vcvars_compiler_update():
    client = TestClient(path_with_spaces=False)
    client.save({"conanfile.txt": "[generators]\nVCVars"})
    client.run('install . -s os=Windows -s compiler=msvc -s compiler.version=193 '
               '-s compiler.cppstd=14 -s compiler.runtime=static '
               '-s compiler.update=3')

    vcvars = client.load("conanvcvars.bat")
    assert 'vcvarsall.bat"  amd64 -vcvars_ver=14.33' in vcvars


@pytest.mark.tool("visual_studio", "17")
@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
def test_vcvars_conf_msvc_update():
    client = TestClient(path_with_spaces=False)
    client.save({"conanfile.txt": "[generators]\nVCVars"})
    client.run('install . -s os=Windows -s compiler=msvc -s compiler.version=193 '
               '-s compiler.cppstd=14 -s compiler.runtime=static '
               '-c tools.microsoft:msvc_update=8.29910')

    vcvars = client.load("conanvcvars.bat")
    assert 'vcvarsall.bat"  amd64 -vcvars_ver=14.38.29910' in vcvars


@pytest.mark.tool("visual_studio", "17")
@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
def test_vcvars_armv8_windows_store():
    client = TestClient(path_with_spaces=False)
    client.save({"conanfile.txt": "[generators]\nVCVars"})
    client.run('install . -s:b os=Windows -s compiler="msvc" -s compiler.version=194 '
               '-s compiler.cppstd=14 -s compiler.runtime=static -s:h arch=armv8 '
               '-s:h os=WindowsStore -s:h os.version=10.0')

    vcvars = client.load("conanvcvars.bat")
    assert 'vcvarsall.bat"  amd64_arm64' in vcvars
