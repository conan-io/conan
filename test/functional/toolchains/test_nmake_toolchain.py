import platform
import textwrap

import pytest

from conan.test.assets.sources import gen_function_cpp
from test.functional.utils import check_exe_run
from conan.test.utils.tools import TestClient


@pytest.mark.parametrize(
    "compiler, version, runtime, cppstd, build_type, defines, cflags, cxxflags, sharedlinkflags, exelinkflags",
    [
        ("msvc", "190", "dynamic", "14", "Release", [], [], [], [], []),
        ("msvc", "190", "dynamic", "14", "Release",
         ["TEST_DEFINITION1", "TEST_DEFINITION2=0", "TEST_DEFINITION3=", "TEST_DEFINITION4=TestPpdValue4",
          "TEST_DEFINITION5=__declspec(dllexport)", "TEST_DEFINITION6=foo bar"],
         ["/GL"], ["/GL"], ["/LTCG"], ["/LTCG"]),
        ("msvc", "191", "static", "17", "Debug", [], [], [], [], []),
    ],
)
@pytest.mark.skipif(platform.system() != "Windows", reason="Only for windows")
def test_toolchain_nmake(compiler, version, runtime, cppstd, build_type,
                         defines, cflags, cxxflags, sharedlinkflags, exelinkflags):
    client = TestClient(path_with_spaces=False)
    settings = {"compiler": compiler,
                "compiler.version": version,
                "compiler.cppstd": cppstd,
                "compiler.runtime": runtime,
                "build_type": build_type,
                "arch": "x86_64"}

    serialize_array = lambda arr: "[{}]".format(",".join([f"'{v}'" for v in arr]))
    conf = {
        "tools.build:defines": serialize_array(defines) if defines else "",
        "tools.build:cflags": serialize_array(cflags) if cflags else "",
        "tools.build:cxxflags": serialize_array(cxxflags) if cxxflags else "",
        "tools.build:sharedlinkflags": serialize_array(sharedlinkflags) if sharedlinkflags else "",
        "tools.build:exelinkflags": serialize_array(exelinkflags) if exelinkflags else "",
    }

    # Build the profile according to the settings provided
    settings = " ".join('-s %s="%s"' % (k, v) for k, v in settings.items() if v)

    client.run("new cmake_lib -d name=dep -d version=1.0")
    conf = " ".join(f'-c {k}="{v}"' for k, v in conf.items() if v)
    client.run(f'create . -tf=\"\" {settings} {conf}'
               f' -c tools.cmake.cmaketoolchain:generator="Visual Studio 15"')

    # Rearrange defines to macro / value dict
    conf_preprocessors = {}
    for define in defines:
        if "=" in define:
            key, value = define.split("=", 1)
            # gen_function_cpp doesn't properly handle empty macros
            if value:
                conf_preprocessors[key] = value
        else:
            conf_preprocessors[define] = "1"

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
          $(CPP) $*.cpp

        simple.exe: simple.obj
          $(CPP) simple.obj
        """)
    client.save({"conanfile.py": conanfile,
                 "makefile": makefile,
                 "simple.cpp": gen_function_cpp(name="main", includes=["dep"], calls=["dep"], preprocessor=conf_preprocessors.keys())},
                clean_first=True)
    client.run(f"build . {settings} {conf}")
    client.run_command("simple.exe")
    assert "dep/1.0" in client.out
    check_exe_run(client.out, "main", "msvc", version, build_type, "x86_64", cppstd, conf_preprocessors)
