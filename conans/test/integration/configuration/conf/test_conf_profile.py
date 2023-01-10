import platform
import textwrap

import pytest

from conans.test.utils.tools import TestClient


@pytest.fixture
def client():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conans import ConanFile
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
        compiler=Visual Studio
        compiler.version=15
        compiler.runtime=MD
        build_type=Release
        """)
    client.save({"myprofile": profile})
    client.run("create . pkg/0.1@ -pr=myprofile")
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
    client.run("create . pkg/0.1@ -pr=myprofile")
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
    client.run("create . pkg/0.1@ -pr=myprofile", assert_error=True)
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
        dep*:tools.microsoft.msbuild:verbosity=Minimal
        """)
    client.save({"myprofile": profile})
    client.run("create . pkg/0.1@ -pr=myprofile")
    assert "/verbosity" not in client.out
    client.run("create . dep/0.1@ -pr=myprofile")
    assert "/verbosity:Minimal" in client.out


def test_config_profile_forbidden(client):
    profile = textwrap.dedent("""\
        [conf]
        cache:verbosity=Minimal
        """)
    client.save({"myprofile": profile})
    client.run("install . pkg/0.1@ -pr=myprofile", assert_error=True)
    assert ("ERROR: Error reading 'myprofile' profile: [conf] "
            "'cache:verbosity' not allowed in profiles" in client.out)


def test_msbuild_config():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conans import ConanFile
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
    client.run("create . pkg/0.1@ -pr=myprofile")
    assert "/verbosity:Minimal" in client.out


@pytest.mark.tool_visual_studio
@pytest.mark.skipif(platform.system() != "Windows", reason="Only for windows")
def test_msbuild_compile_options():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conans import ConanFile

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


def test_config_package_append(client):
    profile1 = textwrap.dedent("""\
        [conf]
        user.myteam:myconf=["a", "b", "c"]
        """)
    profile2 = textwrap.dedent("""\
        include(profile1)
        [conf]
        mypkg*:user.myteam:myconf+=["d"]
        mydep*:user.myteam:myconf=+["e"]
        """)
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            def generate(self):
                self.output.info(f"MYCONF: {self.conf.get('user.myteam:myconf')}")
            def build(self):
                self.output.info(f"MYCONFBUILD: {self.conf.get('user.myteam:myconf')}")
            """)
    client.save({"profile1": profile1,
                 "profile2": profile2,
                 "conanfile.py": conanfile})
    client.run("install . mypkg/0.1@ -pr=profile2")
    assert "conanfile.py (mypkg/0.1): MYCONF: ['a', 'b', 'c', 'd']" in client.out
    client.run("install . mydep/0.1@ -pr=profile2")
    assert "conanfile.py (mydep/0.1): MYCONF: ['e', 'a', 'b', 'c']" in client.out

    client.run("create . mypkg/0.1@ -pr=profile2")
    assert "mypkg/0.1: MYCONFBUILD: ['a', 'b', 'c', 'd']" in client.out
    client.run("create . mydep/0.1@ -pr=profile2")
    assert "mydep/0.1: MYCONFBUILD: ['e', 'a', 'b', 'c']" in client.out
