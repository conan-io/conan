import platform
import textwrap
import os

import pytest

from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() not in ["Windows"], reason="Requires Windows")
@pytest.mark.parametrize("scope", ["build", "run", None])
def test_vcvars_generator(scope):
    client = TestClient(path_with_spaces=False)

    conanfile = textwrap.dedent("""
        from conans import ConanFile
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

    if scope in ("build", None):
        bat_contents = client.load("conanbuild.bat")
        assert "conanvcvars.bat" in bat_contents
    else:
        assert not os.path.exists(os.path.join(client.current_folder, "conanbuild.bat"))


@pytest.mark.skipif(platform.system() not in ["Windows"], reason="Requires Windows")
def test_vcvars_generator_string():
    client = TestClient(path_with_spaces=False)

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class TestConan(ConanFile):
            generators = "VCVars"
            settings = "os", "compiler", "arch", "build_type"
    """)
    client.save({"conanfile.py": conanfile})
    client.run('install . -s os=Windows -s compiler="msvc" -s compiler.version=191 '
               '-s compiler.cppstd=14 -s compiler.runtime=static')

    assert os.path.exists(os.path.join(client.current_folder, "conanvcvars.bat"))


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
def test_vcvars_2015_error():
    # https://github.com/conan-io/conan/issues/9888
    client = TestClient(path_with_spaces=False)

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class TestConan(ConanFile):
            generators = "VCVars"
            settings = "os", "compiler", "arch", "build_type"
    """)
    client.save({"conanfile.py": conanfile})
    client.run('install . -s os=Windows -s compiler="msvc" -s compiler.version=190 '
               '-s compiler.cppstd=14 -s compiler.runtime=static')

    vcvars = client.load("conanvcvars.bat")
    assert 'vcvarsall.bat"  amd64' in vcvars
    assert "-vcvars_ver" not in vcvars


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
def test_vcvars_platform_x86():
    # https://github.com/conan-io/conan/issues/11144
    client = TestClient(path_with_spaces=False)

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class TestConan(ConanFile):
            generators = "VCVars"
            settings = "os", "compiler", "arch", "build_type"
    """)
    client.save({"conanfile.py": conanfile})
    client.run('install . -s os=Windows -s compiler="msvc" -s compiler.version=190 '
               '-s compiler.cppstd=14 -s compiler.runtime=static -s:b arch=x86')

    vcvars = client.load("conanvcvars.bat")
    assert 'vcvarsall.bat"  x86_amd64' in vcvars
    assert "-vcvars_ver" not in vcvars
