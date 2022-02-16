import platform
import textwrap

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


@pytest.fixture
def client():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake

        class Pkg(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            generators = "CMakeToolchain"

            def run(self, cmd):  # INTERCEPTOR of running
                self.output.info("RECIPE-RUN: {}".format(cmd))

            def build(self):
                cmake = CMake(self)
                cmake.build()
        """)
    client.save({"conanfile.py": conanfile})
    return client


def test_cmake_no_config(client):
    profile = textwrap.dedent("""\
        [settings]
        os=Windows
        arch=x86_64
        compiler=Visual Studio
        compiler.version=15
        compiler.runtime=MD
        build_type=Release
        """)
    client.save({"myprofile": profile})
    client.run("create . --name=pkg --version=0.1 -pr=myprofile")
    assert "/verbosity" not in client.out


def test_cmake_config(client):
    profile = textwrap.dedent("""\
        [settings]
        os=Windows
        arch=x86_64
        compiler=Visual Studio
        compiler.version=15
        compiler.runtime=MD
        build_type=Release
        [conf]
        tools.microsoft.msbuild:verbosity=Minimal
        """)
    client.save({"myprofile": profile})
    client.run("create . --name=pkg --version=0.1 -pr=myprofile")
    assert "/verbosity:Minimal" in client.out


def test_cmake_config_error(client):
    profile = textwrap.dedent("""\
        [settings]
        os=Windows
        arch=x86_64
        compiler=Visual Studio
        compiler.version=15
        compiler.runtime=MD
        build_type=Release
        [conf]
        tools.microsoft.msbuild:verbosity=non-existing
        """)
    client.save({"myprofile": profile})
    client.run("create . --name=pkg --version=0.1 -pr=myprofile", assert_error=True)
    assert "Unknown msbuild verbosity: non-existing" in client.out


def test_cmake_config_package(client):
    profile = textwrap.dedent("""\
        [settings]
        os=Windows
        arch=x86_64
        compiler=Visual Studio
        compiler.version=15
        compiler.runtime=MD
        build_type=Release
        [conf]
        dep*/*:tools.microsoft.msbuild:verbosity=Minimal
        """)
    client.save({"myprofile": profile})
    client.run("create . --name=pkg --version=0.1 -pr=myprofile")
    assert "/verbosity" not in client.out
    client.run("create . --name=dep --version=0.1 -pr=myprofile")
    assert "/verbosity:Minimal" in client.out


def test_invalid_profile_package_pattern(client):
    profile = textwrap.dedent("""\
        [settings]
        os=Windows
        arch=x86_64
        compiler=Visual Studio
        compiler.version=15
        compiler.runtime=MD
        build_type=Release
        [conf]
        dep*:tools.microsoft.msbuild:verbosity=Minimal
        """)
    client.save({"myprofile": profile})
    client.run("create . --name=pkg --version=0.1 -pr=myprofile", assert_error=True)
    assert "Error reading 'myprofile' profile: Specify a reference in the conf entry: " \
           "'dep*/*' instead of 'dep*'." in client.out


def test_config_profile_forbidden(client):
    profile = textwrap.dedent("""\
        [conf]
        cache:verbosity=Minimal
        """)
    client.save({"myprofile": profile})
    client.run("install . --name=pkg --version=0.1 -pr=myprofile", assert_error=True)
    assert ("ERROR: Error reading 'myprofile' profile: [conf] "
            "'cache:verbosity' not allowed in profiles" in client.out)


def test_msbuild_config():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.microsoft import MSBuild

        class Pkg(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            def build(self):
                ms = MSBuild(self)
                self.output.info(ms.command("Project.sln"))
        """)
    client.save({"conanfile.py": conanfile})
    profile = textwrap.dedent("""\
        [settings]
        os=Windows
        arch=x86_64
        compiler=Visual Studio
        compiler.version=15
        compiler.runtime=MD
        build_type=Release
        [conf]
        tools.microsoft.msbuild:verbosity=Minimal
        """)
    client.save({"myprofile": profile})
    client.run("create . --name=pkg --version=0.1 -pr=myprofile")
    assert "/verbosity:Minimal" in client.out


@pytest.mark.tool("visual_studio")
@pytest.mark.skipif(platform.system() != "Windows", reason="Only for windows")
def test_msbuild_compile_options():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class Pkg(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            generators = "MSBuildToolchain"
        """)
    client.save({"conanfile.py": conanfile})

    profile = textwrap.dedent("""\
        [settings]
        os=Windows
        arch=x86_64
        compiler=Visual Studio
        compiler.version=15
        compiler.runtime=MD
        build_type=Release
        [conf]
        tools.microsoft.msbuildtoolchain:compile_options={"ExceptionHandling": "Async"}
        """)
    client.save({"myprofile": profile})
    client.run("install . -pr=myprofile")
    msbuild_tool = client.load("conantoolchain_release_x64.props")
    assert "<ExceptionHandling>Async</ExceptionHandling>" in msbuild_tool


def test_conf_package_patterns():
    client = TestClient()
    conanfile = GenConanfile()
    generate = """
    def generate(self):
        value = self.conf["myconfig"]
        self.output.warning("{} Config:{}".format(self.ref.name, value))
"""
    client.save({"dep/conanfile.py": str(conanfile) + generate,
                 "pkg/conanfile.py": str(conanfile.with_requirement("dep/0.1", visible=False)) + generate,
                 "consumer/conanfile.py": str(conanfile.with_requires("pkg/0.1")
                .with_settings("os", "build_type", "arch")) + generate})

    client.run("export dep --name=dep --version=0.1")
    client.run("export pkg --name=pkg --version=0.1")

    # Invalid package namespace, "*" is not a valid reference pattern
    profile = """
    [settings]
    os=Windows
    [conf]
    myconfig=Foo
    """
    client.save({"profile": profile})
    client.run("install consumer --build missing --profile profile", assert_error=True)
    assert "Specify a reference in the [buildenv] entry: '*/*' instead of '*'." in client.out

    # Invalid package namespace, "*foo" is not a valid reference pattern
    profile = """
        include(default)
        [buildenv]
        *foo:myconfig=Foo
        """
    client.save({"profile": profile})
    client.run("install consumer --build --profile profile", assert_error=True)
    assert "Specify a reference in the [buildenv] entry: '*foo/*' instead of '*foo'." in client.out

    # This pattern applies to no package
    profile = """
            include(default)
            [buildenv]
            invented/*:myconfig=Foo
            """
    client.save({"profile": profile})
    client.run("install consumer --build --profile profile")
    assert "WARN: dep Config:None" in client.out
    assert "WARN: pkg Config:None" in client.out
    assert "WARN: None Config:None" in client.out

    # This patterns applies to dep
    profile = """
                include(default)
                [buildenv]
                dep/*:myconfig=Foo
                """
    client.save({"profile": profile})
    client.run("install consumer --build --profile profile")
    assert "WARN: dep Config:Foo" in client.out
    assert "WARN: pkg Config:None" in client.out
    assert "WARN: None Config:None" in client.out

    profile = """
                    include(default)
                    [buildenv]
                    dep/0.1:myconfig=Foo
                    """
    client.save({"profile": profile})
    client.run("install consumer --build --profile profile")
    assert "WARN: dep Config:Foo" in client.out
    assert "WARN: pkg Config:None" in client.out
    assert "WARN: None Config:None" in client.out

    # The global pattern applies to all
    profile = """
                    include(default)
                    [buildenv]
                    dep/*:myconfig=Foo
                    pkg/*:myconfig=Foo
                    myconfig=Var
                    """
    client.save({"profile": profile})
    client.run("install consumer --build --profile profile")
    assert "WARN: dep Config:Var" in client.out
    assert "WARN: pkg Config:Var" in client.out
    assert "WARN: None Config:Var" in client.out

    # "&" pattern for the consumer
    profile = """
                        include(default)
                        [buildenv]
                        dep/*:my_env_var=Foo
                        pkg/*:my_env_var=Foo2
                        &:my_env_var=Var
                        """
    client.save({"profile": profile})
    client.run("install consumer --build --profile profile")
    assert "WARN: dep Config:Foo" in client.out
    assert "WARN: pkg Config:Foo2" in client.out
    assert "WARN: None Config:Var" in client.out
