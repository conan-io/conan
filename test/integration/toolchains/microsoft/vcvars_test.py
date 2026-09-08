import platform
import textwrap
import os

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() not in ["Windows"], reason="Requires Windows")
@pytest.mark.parametrize("scope", ["build", "run", None])
def test_vcvars_generator(scope):
    client = TestClient(path_with_spaces=False)

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.microsoft import VCVars

        class TestConan(ConanFile):
            settings = "os", "compiler", "arch", "build_type"

            def generate(self):
                VCVars(self).generate({})
    """.format('scope="{}"'.format(scope) if scope else ""))

    client.save({"conanfile.py": conanfile})
    client.run('install . -s os=Windows -s compiler="msvc" -s compiler.version=191 '
               '-s compiler.cppstd=14 -s compiler.runtime=static')

    assert os.path.exists(os.path.join(client.current_folder, "conanvcvars.bat"))
    assert r"VC\Auxiliary\Build\vcvarsall.bat" in client.load("conanvcvars.bat")
    bat_contents = client.load("conanbuild.bat")
    if scope in ("build", None):
        assert "conanvcvars.bat" in bat_contents


@pytest.mark.skipif(platform.system() not in ["Windows"], reason="Requires Windows")
def test_vcvars_generator_skip():
    """
    tools.microsoft.msbuild:installation_path=disabled avoids creation of conanvcvars.bat
    """
    client = TestClient()
    client.save({"conanfile.py": GenConanfile().with_generator("VCVars")
                                               .with_settings("os", "compiler",
                                                              "arch", "build_type"),
                 "profile": 'include(default)\n[conf]\ntools.microsoft.msbuild:installation_path='})

    client.run('install . -c tools.microsoft.msbuild:installation_path=""')
    assert not os.path.exists(os.path.join(client.current_folder, "conanvcvars.bat"))
    client.run('install . -pr=profile')
    assert not os.path.exists(os.path.join(client.current_folder, "conanvcvars.bat"))


@pytest.mark.skipif(platform.system() not in ["Linux"], reason="Requires Linux")
def test_vcvars_generator_skip_on_linux():
    """
    Skip creation of conanvcvars.bat on Linux build systems
    """
    client = TestClient()
    client.save({"conanfile.txt": "[generators]\nVCVars"})

    client.run('install . -s os=Windows -s compiler=msvc -s compiler.version=193 '
               '-s compiler.runtime=dynamic')
    assert not os.path.exists(os.path.join(client.current_folder, "conanvcvars.bat"))


@pytest.mark.skipif(platform.system() not in ["Windows"], reason="Requires Windows")
def test_vcvars_generator_string():
    client = TestClient(path_with_spaces=False)
    client.save({"conanfile.txt": "[generators]\nVCVars"})
    client.run('install . -s os=Windows -s compiler="msvc" -s compiler.version=191 '
               '-s compiler.cppstd=14 -s compiler.runtime=static')

    assert os.path.exists(os.path.join(client.current_folder, "conanvcvars.bat"))


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
def test_vcvars_platform_x86():
    # https://github.com/conan-io/conan/issues/11144
    client = TestClient(path_with_spaces=False)
    client.save({"conanfile.txt": "[generators]\nVCVars"})
    client.run('install . -s:b arch=x86')

    vcvars = client.load("conanvcvars.bat")
    assert 'vcvarsall.bat"  x86_amd64' in vcvars


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
def test_vcvars_activation_error_does_not_fail_build():
    """
    https://github.com/conan-io/conan/issues/20311

    ``conanbuild.bat`` calls every registered activation script one after another with
    plain ``call`` statements, without checking the errorlevel in between. So even if
    ``conanvcvars.bat`` correctly fails with a non-zero exit code (e.g. an invalid
    toolset), a later script that runs and succeeds (like the auto-generated
    ``conanbuildenv.bat``) overwrites that errorlevel, and the failure never
    propagates. This reproduces that behavior with simple custom .bat scripts standing
    in for ``conanvcvars.bat`` and ``conanbuildenv.bat``, instead of a real MSVC
    installation.
    """
    client = TestClient(path_with_spaces=False)
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import save

        class Pkg(ConanFile):
            name = "pkg"
            version = "1.0"
            settings = "os", "compiler", "arch", "build_type"

            def generate(self):
                # Emulates a failing vcvarsall.bat: it prints an error message and
                # does exit with a non-zero errorlevel
                save(self, "myvcvars.bat",
                     "@echo off\\necho [ERROR:vcvars.bat] Toolset directory not found\\n"
                     "exit /b 1")
                self.env_scripts.setdefault("build", []).append("myvcvars.bat")
                # Emulates another activation script that runs afterwards, like the
                # auto-generated conanbuildenv.bat, and succeeds
                save(self, "mybuildenv.bat", "echo Running mybuildenv.bat!!!")
                self.env_scripts.setdefault("build", []).append("mybuildenv.bat")

            def build(self):
                self.run("echo Hello")
        """)
    client.save({"conanfile.py": conanfile})
    client.run("create . -s os=Windows -s compiler=msvc -s compiler.version=193 "
               "-s compiler.runtime=dynamic", assert_error=True)
    assert "[ERROR:vcvars.bat] Toolset directory not found" in client.out
    # This is the bug: myvcvars.bat failed with exit code 1, but mybuildenv.bat ran
    # afterwards and succeeded, silently overwriting the errorlevel, so the build
    # still succeeds and "Hello" gets printed instead of the build raising an error
    assert "Running mybuildenv.bat!!!" not in client.out
    assert "ERROR: pkg/1.0: Error in build() method, line 23" in client.out


@pytest.mark.skipif(platform.system() not in ["Windows"], reason="Requires Windows")
def test_vcvars_clang_visual2026():
    client = TestClient(path_with_spaces=False)
    client.save({"conanfile.txt": "[generators]\nVCVars"})
    client.run('install . -s:b os=Windows -s compiler=clang -s compiler.version=20 '
               '-s compiler.cppstd=14 -s compiler.runtime=static -s arch=x86_64 '
               '-s compiler.runtime_version=v145 '
               # Using a known existing path to avoid auto-detection via vswhere
               '-c tools.microsoft.msbuild:installation_path=C:/')

    vcvars = client.load("conanvcvars.bat")
    assert '-vcvars_ver=14.5' in vcvars
