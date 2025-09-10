import textwrap

from conan.test.utils.tools import TestClient


def test_premake_args_without_toolchain():
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
    c.run(
        "build . -s compiler=msvc -s compiler.version=193 -s compiler.runtime=dynamic"
    )
    assert (
        'conanfile.py: Running premake5 --file="myproject.lua" vs2022 --myarg=myvalue!!'
        in c.out
    )


def test_premake_build_without_toolchain():
    tc = TestClient()
    conanfile = textwrap.dedent(
        """
        from conan import ConanFile
        from conan.tools.premake import Premake, PremakeToolchain

        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            def run(self, cmd, *args, **kwargs):
                self.output.info(f"Running {cmd}!!")
            def build(self):
                premake = Premake(self)
                premake.configure()
                premake.build(workspace="App")
                """
    )
    tc.save({"conanfile.py": conanfile})
    tc.run(
        "build . -s compiler=msvc -s compiler.version=193 -s compiler.runtime=dynamic",
        assert_error=True,
    )
    assert "Premake.build() method requires PremakeToolchain to work properly" in tc.out


def test_premake_build():
    tc = TestClient()
    conanfile = textwrap.dedent(
        """
        from conan import ConanFile
        from conan.tools.premake import Premake, PremakeToolchain

        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "PremakeToolchain"
            def run(self, cmd, *args, **kwargs):
                self.output.info(f"Running {cmd}!!")
            def build(self):
                premake = Premake(self)
                premake.configure()
                premake.build(workspace="App")
                """
    )
    tc.save({"conanfile.py": conanfile})
    tc.run(
        "build . -s compiler=gcc -s compiler.version=13 -s compiler.libcxx=libstdc++ -s arch=x86_64 -c tools.build:jobs=4",
    )
    assert 'conanfile.premake5.lua" gmake --arch=x86_64!!' in tc.out
    assert "Running make config=release all -j4!!" in tc.out


def test_premake_build_with_targets():
    tc = TestClient()
    conanfile = textwrap.dedent(
        """
        from conan import ConanFile
        from conan.tools.premake import Premake, PremakeToolchain

        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "PremakeToolchain"
            def run(self, cmd, *args, **kwargs):
                self.output.info(f"Running {cmd}!!")
            def build(self):
                premake = Premake(self)
                premake.configure()
                premake.build(workspace="App", targets=["app", "test"])
                """
    )
    tc.save({"conanfile.py": conanfile})
    tc.run(
        "build . -s compiler=gcc -s compiler.version=13 -s compiler.libcxx=libstdc++ -s arch=armv8 -c tools.build:jobs=42",
    )
    assert 'conanfile.premake5.lua" gmake --arch=arm64!!' in tc.out
    assert "Running make config=release app test -j42!!" in tc.out


def test_premake_msbuild_platform():
    tc = TestClient()
    windows_profile = textwrap.dedent("""
        [settings]
        arch=x86_64
        build_type=Release
        compiler=msvc
        compiler.cppstd=14
        compiler.runtime=dynamic
        compiler.version=194
        os=Windows
    """)

    conanfile = textwrap.dedent(
        """
        from conan import ConanFile
        from conan.tools.premake import Premake, PremakeToolchain

        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "PremakeToolchain"
            def run(self, cmd, *args, **kwargs):
                self.output.info(f"Running {cmd}!!")
            def build(self):
                premake = Premake(self)
                premake.configure()
                premake.build(workspace="App", msbuild_platform="Win64")
                """
    )
    tc.save({"conanfile.py": conanfile, "win": windows_profile})
    tc.run("build . -pr win")
    assert 'conanfile.premake5.lua" vs2022 --arch=x86_64!!' in tc.out
    assert 'Running msbuild.exe "App.sln" -p:Configuration="Release" -p:Platform=Win64!!' in tc.out
