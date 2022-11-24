import platform
import textwrap

import pytest

from conans.test.assets.sources import gen_function_cpp
from conans.test.functional.utils import check_exe_run
from conans.test.utils.tools import TestClient


@pytest.mark.parametrize("compiler, version, runtime, cppstd, build_type",
                         [("msvc", "190", "dynamic", "14", "Release"),
                          ("msvc", "191", "static", "17", "Debug")])
@pytest.mark.skipif(platform.system() != "Windows", reason="Only for windows")
def test_toolchain_nmake(compiler, version, runtime, cppstd, build_type):
    client = TestClient(path_with_spaces=False)
    settings = {"compiler": compiler,
                "compiler.version": version,
                "compiler.cppstd": cppstd,
                "compiler.runtime": runtime,
                "build_type": build_type,
                "arch": "x86_64"}

    # Build the profile according to the settings provided
    settings = " ".join('-s %s="%s"' % (k, v) for k, v in settings.items() if v)
    client.run("new dep/1.0 -m=cmake_lib")
    client.run(f'create . -tf=None {settings} '
               f'-c tools.cmake.cmaketoolchain:generator="Visual Studio 15"')

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            requires = "dep/1.0"
            generators = "NMakeToolchain", "NMakeDeps"

            def build(self):
                self.run(f"nmake /f makefile")
            """)
    makefile = textwrap.dedent("""\
        all: simple.exe

        .cpp.obj:
          cl $(cppflags) $*.cpp

        simple.exe: simple.obj
          cl $(cppflags) simple.obj
        """)
    client.save({"conanfile.py": conanfile,
                 "makefile": makefile,
                 "simple.cpp": gen_function_cpp(name="main", includes=["dep"], calls=["dep"])},
                clean_first=True)
    client.run("install . {}".format(settings))
    client.run("build .")
    client.run_command("simple.exe")
    assert "dep/1.0" in client.out
    check_exe_run(client.out, "main", "msvc", version, build_type, "x86_64", cppstd)
