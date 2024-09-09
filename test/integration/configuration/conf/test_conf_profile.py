import textwrap

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


@pytest.fixture
def client():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake

        class Pkg(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            generators = "CMakeToolchain"

            def run(self, cmd, env=None, **kwargs):  # INTERCEPTOR of running
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
        tools.build:verbosity=quiet
        """)
    client.save({"myprofile": profile})
    client.run("create . --name=pkg --version=0.1 -pr=myprofile")
    assert "/verbosity:Quiet" in client.out


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
        tools.build:verbosity=non-existing
        """)
    client.save({"myprofile": profile})
    client.run("create . --name=pkg --version=0.1 -pr=myprofile", assert_error=True)
    assert "Unknown value 'non-existing' for 'tools.build:verbosity'" in client.out


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
        dep*:tools.build:verbosity=quiet
        """)
    client.save({"myprofile": profile})
    client.run("create . --name=pkg --version=0.1 -pr=myprofile")
    assert "/verbosity" not in client.out
    client.run("create . --name=dep --version=0.1 -pr=myprofile")
    assert "/verbosity:Quiet" in client.out


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
        tools.build:verbosity=quiet
        """)
    client.save({"myprofile": profile})
    client.run("create . --name=pkg --version=0.1 -pr=myprofile")
    assert "/verbosity:Quiet" in client.out
    client.run("create . --name=dep --version=0.1 -pr=myprofile")
    assert "/verbosity:Quiet" in client.out


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
        tools.build:verbosity=quiet
        """)
    client.save({"myprofile": profile})
    client.run("create . --name=pkg --version=0.1 -pr=myprofile")
    assert "/verbosity:Quiet" in client.out


def test_msbuild_compile_options():
    # This works in all platforms because MSBuildToolchain works even in Linux, it will
    # just skip generating the conanvcvars.bat
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
    client.run("install . --name=mypkg --version=0.1 -pr=profile2")
    assert "conanfile.py (mypkg/0.1): MYCONF: ['a', 'b', 'c', 'd']" in client.out
    client.run("install . --name=mydep --version=0.1 -pr=profile2")
    assert "conanfile.py (mydep/0.1): MYCONF: ['e', 'a', 'b', 'c']" in client.out

    client.run("create . --name=mypkg --version=0.1 -pr=profile2")
    assert "mypkg/0.1: MYCONFBUILD: ['a', 'b', 'c', 'd']" in client.out
    client.run("create . --name=mydep --version=0.1 -pr=profile2")
    assert "mydep/0.1: MYCONFBUILD: ['e', 'a', 'b', 'c']" in client.out


def test_conf_patterns_user_channel():
    # https://github.com/conan-io/conan/issues/14139
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class Pkg(ConanFile):
            def configure(self):
                self.output.info(f"CONF: {self.conf.get('user.myteam:myconf')}")
                self.output.info(f"CONF2: {self.conf.get('user.myteam:myconf2')}")
        """)
    profile = textwrap.dedent("""\
        [conf]
        user.myteam:myconf=myvalue1
        user.myteam:myconf2=other1
        *@user/channel:user.myteam:myconf=myvalue2
        *@*/*:user.myteam:myconf2=other2
        """)
    client.save({"dep/conanfile.py": conanfile,
                 "app/conanfile.py": GenConanfile().with_requires("dep1/0.1",
                                                                  "dep2/0.1@user/channel"),
                 "profile": profile})

    client.run("create dep --name=dep1 --version=0.1")
    client.run("create dep --name=dep2 --version=0.1 --user=user --channel=channel")
    client.run("install app -pr=profile")
    assert "dep1/0.1: CONF: myvalue1" in client.out
    assert "dep2/0.1@user/channel: CONF: myvalue2" in client.out
    assert "dep1/0.1: CONF2: other1" in client.out
    assert "dep2/0.1@user/channel: CONF2: other2" in client.out
