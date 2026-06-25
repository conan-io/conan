import json
import os
import platform
import textwrap

import pytest

from conan.internal.paths import CONANFILE
from conan.test.utils.tools import TestClient, GenConanfile


class TestBuildRequires:

    @pytest.fixture()
    def client(self):
        c = TestClient()
        tool_conanfile = textwrap.dedent("""
            import os
            from conan import ConanFile
            from conan.tools.files import copy

            class tool(ConanFile):
                name = "tool"
                version = "0.1"
                exports_sources = "mytool*"

                def package(self):
                    copy(self, "mytool*", self.source_folder, self.package_folder)

                def package_info(self):
                    self.buildenv_info.append_path("PATH", self.package_folder)
            """)
        name = "mytool.bat" if platform.system() == "Windows" else "mytool"
        c.save({CONANFILE: tool_conanfile,
                name: "echo Hello World!"}, clean_first=True)
        os.chmod(os.path.join(c.current_folder, name), 0o777)
        c.run("export . --user=lasote --channel=stable")

        lib_conanfile = textwrap.dedent("""
            from conan import ConanFile

            class mylib(ConanFile):
                name = "mylib"
                version = "0.1"

                def build(self):
                    self.run("mytool")
            """)
        profile = """
            [tool_requires]
            tool/0.1@lasote/stable
            nonexistingpattern*: sometool/1.2@user/channel
            """

        profile2 = """
            [tool_requires]
            tool/0.1@lasote/stable
            nonexistingpattern*: sometool/1.2@user/channel
            """

        test_conanfile = textwrap.dedent("""
           from conan import ConanFile

           class Testmylib(ConanFile):

               def build(self):
                   self.run("mytool")
               def test(self):
                   pass
           """)
        c.save({CONANFILE: lib_conanfile,
                "test_package/conanfile.py": test_conanfile,
                "profile.txt": profile,
                "profile2.txt": profile2}, clean_first=True)
        return c

    def test_profile_requires(self, client):
        """
        cli -(tool-requires)-> tool/0.1
          \\--(requires)->mylib/0.1 -(tool_requires)->tool/0.1 (skipped)
        """
        client.run("export . --user=lasote --channel=stable")
        client.run("install --requires=mylib/0.1@lasote/stable "
                   "--profile ./profile.txt --build missing")
        assert "Hello World!" in client.out

        client.run("install --requires=mylib/0.1@lasote/stable --profile ./profile2.txt --build='*'")
        assert "Hello World!" in client.out

    def test_profile_open_requires(self, client):
        client.run("build . --profile ./profile.txt --build missing")
        assert "Hello World!" in client.out

    def test_build_mode_requires(self, client):
        client.run("install . --profile ./profile.txt", assert_error=True)
        assert "ERROR: Missing prebuilt package for 'tool/0.1@lasote/stable'" in client.out
        client.run("install . --profile ./profile.txt --build=Pythontool", assert_error=True)
        assert "ERROR: Missing prebuilt package for 'tool/0.1@lasote/stable'" in client.out
        client.run("install . --profile ./profile.txt --build=tool/0.1*")
        assert "tool/0.1@lasote/stable: Created package" in client.out

        # now remove packages, ensure --build=missing also creates them
        client.run('remove "*:*" -c')
        client.run("install . --profile ./profile.txt --build=missing")
        assert "tool/0.1@lasote/stable: Created package" in client.out

    def test_profile_test_requires(self, client):
        client.run("create . --profile ./profile.txt --build missing")
        assert 2 == str(client.out).splitlines().count("Hello World!")

    def test_consumer_patterns(self, client):
        profile_patterns = """
            [tool_requires]
            &: tool/0.1@lasote/stable
            nonexistingpattern*: sometool/1.2@user/channel
            """
        client.save({CONANFILE: GenConanfile("mylib", "0.1"),
                     "profile.txt": profile_patterns})
        client.run("create . --profile=./profile.txt --build=missing")
        assert 1 == str(client.out).splitlines().count("Hello World!")

    def test_build_requires_options(self):
        client = TestClient()
        client.save({CONANFILE: GenConanfile("mytool", "0.1")})
        client.run("export . --user=lasote --channel=stable")

        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class mylib(ConanFile):
                name = "mylib"
                version = "0.1"
                build_requires = "mytool/0.1@lasote/stable"
                options = {"coverage": [True, False]}
                def build(self):
                    self.output.info("Coverage %s" % self.options.coverage)
            """)
        client.save({CONANFILE: conanfile}, clean_first=True)
        client.run("build . -o mylib*:coverage=True --build missing")
        client.assert_listed_require({"mytool/0.1@lasote/stable": "Cache"}, build=True)
        assert "conanfile.py (mylib/0.1): Coverage True" in client.out

        client.save({CONANFILE: conanfile}, clean_first=True)
        client.run("build . -o coverage=True")
        client.assert_listed_require({"mytool/0.1@lasote/stable": "Cache"}, build=True)
        assert "mytool/0.1@lasote/stable: Already installed!" in client.out
        assert "conanfile.py (mylib/0.1): Coverage True" in client.out


def test_consumer_patterns_loop_error():
    client = TestClient()

    profile_patterns = textwrap.dedent("""
        include(default)
        [tool_requires]
        tool1/1.0
        tool2/1.0
        """)
    client.save({"tool1/conanfile.py": GenConanfile(),
                 "tool2/conanfile.py": GenConanfile().with_build_requires("tool1/1.0"),
                 "consumer/conanfile.py": GenConanfile(),
                 "profile.txt": profile_patterns})

    client.run("export tool1 --name=tool1 --version=1.0")
    client.run("export tool2 --name=tool2 --version=1.0")
    client.run("install consumer --build=missing -pr:b=profile.txt -pr:h=profile.txt",
               assert_error=True)
    assert "There is a cycle/loop in the graph" in client.out

    # we can fix it with the negation
    profile_patterns = textwrap.dedent("""
        include(default)
        [tool_requires]
        tool1/1.0
        !tool1*:tool2/1.0
        """)
    client.save({"profile.txt": profile_patterns})

    client.run("install consumer --build=missing -pr:b=profile.txt -pr:h=profile.txt")
    assert "tool1/1.0: Created package" in client.out
    assert "tool2/1.0: Created package" in client.out


def test_tool_requires_revision_profile():
    # We shoul be able to explicitly [tool_require] a recipe revision in the profile
    c = TestClient()
    build_profile = textwrap.dedent("""\
        [settings]
        os=Linux
        [tool_requires]
        *:tool/0.1#2d65f1b4af1ce59028f96adbfe7ed5a2
        """)
    c.save({"tool/conanfile.py": GenConanfile("tool", "0.1"),
            "cmake/conanfile.py": GenConanfile("cmake", "0.1"),
            "app/conanfile.py": GenConanfile("app", "0.1").with_tool_requires("cmake/0.1"),
            "build_profile": build_profile})
    c.run("export tool")
    rev1 = c.exported_recipe_revision()
    assert rev1 == "2d65f1b4af1ce59028f96adbfe7ed5a2"
    # Create a new tool revision to proof that we can still require the old one
    c.save({"tool/conanfile.py": GenConanfile("tool", "0.1").with_class_attribute("myvar=42")})
    c.run("export tool")
    rev2 = c.exported_recipe_revision()
    assert rev2 != rev1
    c.run("export cmake")
    c.run("graph info app -pr:b=build_profile --build=*")
    assert f"tool/0.1#{rev1}" in c.out
    assert rev2 not in c.out


def test_tool_requires_version_range_loop():
    # https://github.com/conan-io/conan/issues/17930
    c = TestClient(light=True)
    build_profile = textwrap.dedent("""\
        [settings]
        os=Linux
        [tool_requires]
        tool/[>=1.0 <2]
        """)
    c.save({"tool/conanfile.py": GenConanfile("tool", "1.1"),
            "app/conanfile.py": GenConanfile("app", "0.1").with_tool_requires("tool/1.1"),
            "build_profile": build_profile})
    c.run("create tool")
    c.run("install app -pr:b=build_profile")
    assert "tool/1.1" in c.out  # It is skipped


def test_profile_tool_requires_negated_or_patterns():
    """Negated [tool_requires] patterns may use | so the rule applies
    if the ref matches none of the branches."""
    c = TestClient(light=True)
    profile_build = textwrap.dedent("""\
        [settings]
        os=Linux

        [tool_requires]
        mold/1.0
        !(zlib*|mold*):cmake/1.0
        """)
    profile = textwrap.dedent("""\
        [tool_requires]
        mold/1.0
        cmake/1.0
        gcc/1.0
            """)
    c.save({"mold/conanfile.py": GenConanfile("mold", "1.0"),
            "zlib/conanfile.py": GenConanfile("zlib", "1.0"),
            "cmake/conanfile.py": GenConanfile("cmake", "1.0").with_tool_requires("zlib/1.0"),
            "gcc/conanfile.py": GenConanfile("gcc", "1.0").with_tool_requires("zlib/1.0"),
            "app/conanfile.py": GenConanfile("app", "1.0"),
            "profile_build": profile_build,
            "profile": profile})
    c.run("create mold")
    c.run("create zlib")
    c.run("create cmake")
    c.run("create gcc")
    c.run("graph info app -pr=profile -pr:b=profile_build --format=json")
    graph = json.loads(c.stdout)
    assert len(graph["graph"]["nodes"]) == 14
    c.assert_listed_require({"cmake/1.0": "Cache",
                             "gcc/1.0": "Cache",
                             "mold/1.0": "Cache",
                             "zlib/1.0": "Cache"}, build=True)
