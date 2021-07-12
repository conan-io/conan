import platform
import textwrap
import os

import pytest

from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() not in ["Windows"], reason="Requires Windows")
@pytest.mark.parametrize("auto_activate", [False, True, None])
def test_vcvars_generator(auto_activate):
    client = TestClient(path_with_spaces=False)

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.microsoft import VCVars

        class TestConan(ConanFile):
            settings = "os", "compiler", "arch", "build_type"

            def generate(self):
                VCVars(self).generate({})
    """.format("True" if auto_activate else "False" if auto_activate is False else ""))

    client.save({"conanfile.py": conanfile})
    client.run('install . -s os=Windows -s compiler="msvc" -s compiler.version=19.1 '
               '-s compiler.cppstd=14 -s compiler.runtime=static')

    assert os.path.exists(os.path.join(client.current_folder, "conanvcvars.bat"))

    if auto_activate is True or auto_activate is None:
        bat_contents = client.load("conanenv.bat")
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
