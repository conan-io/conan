import textwrap

from conan.test.utils.tools import TestClient

def test_premake_args():
    tc = TestClient(path_with_spaces=False)
    conanfile = textwrap.dedent(
        """
        from conan import ConanFile
        from conan.tools.premake import Premake, PremakeToolchain

        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            def run(self, cmd, *args, **kwargs):
                self.output.info(f"Running {cmd}!!")
            def generate(self):
                toolchain = PremakeToolchain(self)
                toolchain.generate()
            def build(self):
                premake = Premake(self)
                premake.luafile = "myproject.lua"
                premake.arguments = {"myarg": "myvalue"}
                premake.configure()
                """
    )
    tc.save({"conanfile.py": conanfile})
    tc.run(
        "build . -s compiler=msvc -s compiler.version=193 -s compiler.runtime=dynamic"
    )
    assert "conanfile.py: Running premake5" in tc.out
    print(tc.out)
    assert "conanfile.premake5.lua\" vs2022 --myarg=myvalue!!" in tc.out
