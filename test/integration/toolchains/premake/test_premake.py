import textwrap

from conan.test.utils.tools import TestClient


def test_premake_args():
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.premake import Premake

        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            def run(self, cmd, *args, **kwargs):
                self.output.info(f"Running {cmd}!!")
            def build(self):
                premake = Premake(self)
                premake.luafile = "myproject.lua"
                premake.arguments = {"myarg": "myvalue"}
                premake.configure()
                """)
    c.save({"conanfile.py": conanfile})
    c.run("build . -s compiler=msvc -s compiler.version=193 -s compiler.runtime=dynamic")
    assert "conanfile.py: Running premake5 --file=myproject.lua vs2022 --myarg=myvalue!!" in c.out
