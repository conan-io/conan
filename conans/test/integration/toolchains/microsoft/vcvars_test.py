import platform
import textwrap
import os

import pytest

from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() not in ["Windows"], reason="Requires Windows")
@pytest.mark.parametrize("group", ["build", "run", None])
def test_vcvars_generator(group):
    client = TestClient(path_with_spaces=False)

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.microsoft import VCVars

        class TestConan(ConanFile):
            settings = "os", "compiler", "arch", "build_type"

            def generate(self):
                VCVars(self).generate({})
    """.format('group="{}"'.format(group) if group else ""))

    client.save({"conanfile.py": conanfile})
    client.run('install . -s os=Windows -s compiler="msvc" -s compiler.version=19.1 '
               '-s compiler.cppstd=14 -s compiler.runtime=static')

    assert os.path.exists(os.path.join(client.current_folder, "conanvcvars.bat"))

    if group in ("build", None):
        bat_contents = client.load("conanbuild.bat")
        assert "conanvcvars.bat" in bat_contents
    else:
        assert not os.path.exists(os.path.join(client.current_folder, "conanenv.bat"))


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
    client.run('install . -s os=Windows -s compiler="msvc" -s compiler.version=19.1 '
               '-s compiler.cppstd=14 -s compiler.runtime=static')

    assert os.path.exists(os.path.join(client.current_folder, "conanvcvars.bat"))
