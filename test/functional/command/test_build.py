import json
import os
import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_build_different_folders():
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile

        class AConan(ConanFile):

            def build(self):
                self.output.warning("Build folder=>%s" % self.build_folder)
                self.output.warning("Src folder=>%s" % self.source_folder)
                assert(os.path.exists(self.build_folder))
                assert(os.path.exists(self.source_folder))
    """)

    client = TestClient()
    client.save({"conanfile.py": conanfile})
    with client.chdir("build1"):
        client.run("install ..")
    # Try relative to cwd
    client.run("build . --output-folder build2")
    assert "Build folder=>%s" % os.path.join(client.current_folder, "build2") in client.out
    assert "Src folder=>%s" % client.current_folder in client.out


def test_build_dots_names():
    client = TestClient()
    conanfile_dep = textwrap.dedent("""
        from conan import ConanFile

        class AConan(ConanFile):
            pass
    """)
    client.save({"conanfile.py": conanfile_dep})
    client.run("create . --name=hello.pkg --version=0.1 --user=lasote --channel=testing --format=json",
               redirect_stdout="hello.pkg.json")
    hellopkg_result = json.loads(client.load("hello.pkg.json"))
    client.run("create . --name=hello-tools --version=0.1 --user=lasote --channel=testing --format=json",
               redirect_stdout="hello-tools.json")
    hellotools_result = json.loads(client.load("hello-tools.json"))
    conanfile_scope_env = textwrap.dedent("""
        from conan import ConanFile

        class AConan(ConanFile):
            requires = "hello.pkg/0.1@lasote/testing", "hello-tools/0.1@lasote/testing"

            def generate(self):
                self.output.info("HELLO ROOT PATH: %s" %
                    self.dependencies["hello.pkg"].package_folder)
                self.output.info("HELLO ROOT PATH: %s" %
                    self.dependencies["hello-tools"].package_folder)

            def build(self):
                pass

    """)
    client.save({"conanfile.py": conanfile_scope_env}, clean_first=True)
    client.run("build conanfile.py --build=missing")

    assert hellopkg_result["graph"]["nodes"]["1"]["package_folder"] in client.out
    assert hellotools_result["graph"]["nodes"]["1"]["package_folder"] in client.out


def test_build_with_deps_env_info():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class AConan(ConanFile):
            name = "lib"
            version = "1.0"

            def package_info(self):
                self.buildenv_info.define("MYVAR", "23")

    """)
    client.save({"conanfile.py": conanfile})
    client.run("export . --user=lasote --channel=stable")

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.env import VirtualBuildEnv
        import os

        class AConan(ConanFile):
            build_requires = "lib/1.0@lasote/stable"

            def build(self):
                build_env = VirtualBuildEnv(self).vars()
                assert build_env.get("MYVAR") == "23"
                with build_env.apply():
                    assert(os.environ["MYVAR"] == "23")
    """)
    client.save({"conanfile.py": conanfile}, clean_first=True)
    client.run("build . --build missing")


def test_build_single_full_reference():
    client = TestClient()
    client.save({"conanfile.py": GenConanfile("foo", "1.0")})
    client.run("create . --build='*'")
    assert "foo/1.0: Forced build from source" in client.out


def test_build_multiple_full_reference():
    client = TestClient()
    client.save({"conanfile.py": GenConanfile("foo", "1.0")})
    client.run("create .")
    client.save({"conanfile.py": GenConanfile("bar", "1.0").with_requires("foo/1.0")})
    client.run("create --build foo/1.0@ --build bar/1.0@ .")
    assert "foo/1.0: Forced build from source" in client.out
    assert "bar/1.0: Forced build from source" in client.out


def test_debug_build_release_deps():
    # https://github.com/conan-io/conan/issues/2899
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Conan(ConanFile):
            name = "{name}"
            {requires}
            settings = "build_type"
            def build(self):
                self.output.info("BUILD: %s BuildType=%s!"
                                 % (self.name, self.settings.build_type))
            def package_info(self):
                self.output.info("PACKAGE_INFO: %s BuildType=%s!"
                                 % (self.name, self.settings.build_type))
        """)
    client.save({"conanfile.py": conanfile.format(name="dep", requires="")})
    client.run("create . --name=dep --version=0.1 --user=user --channel=testing -s build_type=Release")
    client.save({"conanfile.py": conanfile.format(name="mypkg", requires="requires = 'dep/0.1@user/testing'")})
    client.run("build . -s mypkg/*:build_type=Debug -s build_type=Release")
    assert "dep/0.1@user/testing: PACKAGE_INFO: dep BuildType=Release!" in client.out
    assert "conanfile.py (mypkg/None): BUILD: mypkg BuildType=Debug!" in client.out

