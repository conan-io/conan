import os
import textwrap

import pytest

from conan.test.assets.sources import gen_function_cpp, gen_function_h
from conan.test.utils.tools import TestClient
from test.functional.toolchains.meson._base import check_binary


class TestMesonPreprocessorDefinitionsTest:
    _conanfile_py = textwrap.dedent("""
    from conan import ConanFile
    from conan.tools.meson import Meson, MesonToolchain


    class App(ConanFile):
        settings = "os", "arch", "compiler", "build_type"
        options = {"shared": [True, False], "fPIC": [True, False]}
        default_options = {"shared": False, "fPIC": True}

        def config_options(self):
            if self.settings.os == "Windows":
                del self.options.fPIC

        def layout(self):
            self.folders.build = "build"

        def generate(self):
            tc = MesonToolchain(self)
    preprocessor_definitions
            tc.generate()

        def build(self):
            meson = Meson(self)
            meson.configure()
            meson.build()
    """)

    _meson_build = textwrap.dedent("""
    project('tutorial', 'cpp')
    hello = library('hello', 'hello.cpp')
    executable('demo', 'main.cpp', link_with: hello)
    """)

    def _inject_definitions(self, content: str, defines: dict) -> str:
        lines = []
        for define, value in defines.items():
            lines.append(f"        tc.preprocessor_definitions['{define}'] = {value}")
        return content.replace("preprocessor_definitions", "\n".join(lines))

    @pytest.mark.tool("ninja")
    @pytest.mark.tool("meson")
    @pytest.mark.parametrize("defines", [{"TEST_DEFINITION1": '"TestPpdValue1"', "TEST_DEFINITION2": '"TestPpdValue2"'},
                                         {"DEADBEEF": 3735928495, "CAFED00D": 3405697037},
                                         {"DEAD10CC": None},
                                         {"BAADF00D": True, "BAD22222": False}])
    def test_build(self, defines):
        hello_h = gen_function_h(name="hello")
        hello_cpp = gen_function_cpp(name="hello",
                                     preprocessor=defines.keys())
        app = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])

        conanfile = self._inject_definitions(self._conanfile_py, defines)

        t = TestClient()
        t.save({"conanfile.py": conanfile,
                "meson.build": self._meson_build,
                "hello.h": hello_h,
                "hello.cpp": hello_cpp,
                "main.cpp": app})

        t.run("install .")

        content = t.load("conan_meson_native.ini")

        assert "[built-in options]" in content
        assert "buildtype = 'release'" in content

        definitions = []
        for define, value in defines.items():
            if value is None:
                definitions.append(f"'-D{define}'")
            elif isinstance(value, bool):
                expected_value = "1" if value else "0"
                definitions.append(f"'-D{define}={expected_value}'")
            elif isinstance(value, str):
                definitions.append(f"'-D{define}={value}'")
            elif isinstance(value, int):
                definitions.append(f"'-D{define}={value}'")
        assert f"preprocessor_definitions = [{', '.join(definitions)}]" in content

        t.run("build .")
        t.run_command(os.path.join("build", "demo"))

        assert "hello: Release!" in t.out
        for define, value in defines.items():
            if value is None:
                assert f"{define}" in t.out
            elif isinstance(value, bool):
                expected_value = "1" if value else "0"
                assert f"{define}={expected_value}" in t.out
            elif isinstance(value, str):
                value = value.replace('"', '')
                assert f"{define}: {value}" in t.out
            elif isinstance(value, int):
                assert f"{define}: {value}" in t.out

        check_binary(t)
