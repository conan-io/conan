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

            def run(self, cmd, env=None):  # INTERCEPTOR of running
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
        compiler=msvc
        compiler.version=191
        compiler.runtime=dynamic
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
        compiler=msvc
        compiler.version=191
        compiler.runtime=dynamic
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
        compiler=msvc
        compiler.version=191
        compiler.runtime=dynamic
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
        compiler=msvc
        compiler.version=191
        compiler.runtime=dynamic
        build_type=Release
        [conf]
        dep*:tools.microsoft.msbuild:verbosity=Minimal
        """)
    client.save({"myprofile": profile})
    client.run("create . --name=pkg --version=0.1 -pr=myprofile")
    assert "/verbosity" not in client.out
    client.run("create . --name=dep --version=0.1 -pr=myprofile")
    assert "/verbosity:Minimal" in client.out


def test_cmake_config_package_not_scoped(client):
    profile = textwrap.dedent("""\
        [settings]
        os=Windows
        arch=x86_64
        compiler=msvc
        compiler.version=191
        compiler.runtime=dynamic
        build_type=Release
        [conf]
        tools.microsoft.msbuild:verbosity=Minimal
        """)
    client.save({"myprofile": profile})
    client.run("create . --name=pkg --version=0.1 -pr=myprofile")
    assert "/verbosity:Minimal" in client.out
    client.run("create . --name=dep --version=0.1 -pr=myprofile")
    assert "/verbosity:Minimal" in client.out


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
        compiler=msvc
        compiler.version=191
        compiler.runtime=dynamic
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
        compiler=msvc
        compiler.version=191
        compiler.runtime=dynamic
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
        value = self.conf.get("user.build:myconfig")
        self.output.warning("{} Config:{}".format(self.ref.name, value))
"""
    client.save({"dep/conanfile.py": str(conanfile) + generate,
                 "pkg/conanfile.py": str(conanfile.with_requirement("dep/0.1", visible=False)) + generate,
                 "consumer/conanfile.py": str(conanfile.with_requires("pkg/0.1")
                .with_settings("os", "build_type")) + generate})

    client.run("export dep --name=dep --version=0.1")
    client.run("export pkg --name=pkg --version=0.1")

    # This pattern applies to no package
    profile = """
    [settings]
    os=Windows
    [conf]
    invented/*:user.build:myconfig=Foo
    """
    client.save({"profile": profile})
    client.run("install consumer --build=* --profile profile")
    assert "WARN: dep Config:None" in client.out
    assert "WARN: pkg Config:None" in client.out
    assert "WARN: None Config:None" in client.out

    # This patterns applies to dep
    profile = """
    [settings]
    os=Windows
    [conf]
    dep/*:user.build:myconfig=Foo
    """
    client.save({"profile": profile})
    client.run("install consumer --build='*' --profile profile")
    assert "WARN: dep Config:Foo" in client.out
    assert "WARN: pkg Config:None" in client.out
    assert "WARN: None Config:None" in client.out

    profile = """
    [settings]
    os=Windows
    [conf]
    dep/0.1:user.build:myconfig=Foo
    """
    client.save({"profile": profile})
    client.run("install consumer --build='*' --profile profile")
    assert "WARN: dep Config:Foo" in client.out
    assert "WARN: pkg Config:None" in client.out
    assert "WARN: None Config:None" in client.out

    # The global pattern applies to all
    profile = """
    [settings]
    os=Windows
    [conf]
    dep/*:user.build:myconfig=Foo
    pkg/*:user.build:myconfig=Foo2
    user.build:myconfig=Var
    """
    client.save({"profile": profile})
    client.run("install consumer --build='*' --profile profile")
    assert "WARN: dep Config:Var" in client.out
    assert "WARN: pkg Config:Var" in client.out
    assert "WARN: None Config:Var" in client.out

    # "&" pattern for the consumer
    profile = """
    [settings]
    os=Windows
    [conf]
    dep/*:user.build:myconfig=Foo
    pkg/*:user.build:myconfig=Foo2
    &:user.build:myconfig=Var
    """

    client.save({"profile": profile})
    client.run("install consumer --build='*' --profile profile")
    assert "WARN: dep Config:Foo" in client.out
    assert "WARN: pkg Config:Foo2" in client.out
    assert "WARN: None Config:Var" in client.out
