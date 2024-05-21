import os
import platform
import sys

import pytest

from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient

import textwrap

_path_chars = "päthñç$"


@pytest.fixture(scope="module")
def client_with_special_chars():
    """ the path with special characters is creating a conanbuild.bat that fails
    """
    cache_folder = os.path.join(temp_folder(), _path_chars)
    current_folder = os.path.join(temp_folder(), _path_chars)
    c = TestClient(cache_folder, current_folder)

    tool = textwrap.dedent(r"""
        import os
        from conan import ConanFile
        from conan.tools.files import save, chdir
        class Pkg(ConanFile):
            name = "mytool"
            version = "1.0"
            def package(self):
                with chdir(self, self.package_folder):
                    echo = "@echo off\necho MYTOOL WORKS!!"
                    save(self, "bin/mytool.bat", echo)
                    save(self, "bin/mytool.sh", echo)
                    os.chmod("bin/mytool.sh", 0o777)
            """)
    c.save({"conanfile.py": tool})
    c.run("create .")

    conan_file = textwrap.dedent("""
        import platform
        from conan import ConanFile

        class App(ConanFile):
            name="failure"
            version="0.1"
            settings = 'os', 'arch', 'compiler', 'build_type'
            generators = "VirtualBuildEnv"
            tool_requires = "mytool/1.0"
            apply_env = False # SUPER IMPORTANT, DO NOT REMOVE

            def build(self):
                mycmd = "mytool.bat" if platform.system() == "Windows" else "mytool.sh"
                self.run(mycmd)
        """)
    c.save({"conanfile.py": conan_file})
    return c


@pytest.mark.skipif(platform.system() == "Linux" and sys.version_info.minor <= 6,
                    reason="It is failing in CI in python3.6 Linux docker image")
def test_reuse_buildenv(client_with_special_chars):
    c = client_with_special_chars
    # Need the 2 profile to work correctly buildenv
    c.run("create .")
    assert _path_chars in c.out
    assert "MYTOOL WORKS!!" in c.out


@pytest.mark.skipif(platform.system() != "Windows", reason="powershell only win")
def test_reuse_buildenv_powershell(client_with_special_chars):
    c = client_with_special_chars
    c.run("create . -c tools.env.virtualenv:powershell=True")
    assert _path_chars in c.out
    assert "MYTOOL WORKS!!" in c.out
