import os
import platform
import textwrap
import unittest

from conan.internal.paths import CONANFILE
from conan.test.utils.tools import TestClient, GenConanfile


tool_conanfile = """
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
"""

lib_conanfile = """
from conan import ConanFile

class mylib(ConanFile):
    name = "mylib"
    version = "0.1"

    def build(self):
        self.run("mytool")
"""

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


class BuildRequiresTest(unittest.TestCase):

    def _create(self, client):
        name = "mytool.bat" if platform.system() == "Windows" else "mytool"
        client.save({CONANFILE: tool_conanfile,
                     name: "echo Hello World!"}, clean_first=True)
        os.chmod(os.path.join(client.current_folder, name), 0o777)
        client.run("export . --user=lasote --channel=stable")

    def test_profile_requires(self):
        """
        cli -(tool-requires)-> tool/0.1
          \\--(requires)->mylib/0.1 -(tool_requires)->tool/0.1 (skipped)
        """
        client = TestClient()
        self._create(client)

        client.save({CONANFILE: lib_conanfile,
                     "profile.txt": profile,
                     "profile2.txt": profile2}, clean_first=True)
        client.run("export . --user=lasote --channel=stable")
        client.run("install --requires=mylib/0.1@lasote/stable --profile ./profile.txt --build missing")
        self.assertIn("Hello World!", client.out)

        client.run("install --requires=mylib/0.1@lasote/stable --profile ./profile2.txt --build='*'")
        self.assertIn("Hello World!", client.out)

    def test_profile_open_requires(self):
        client = TestClient()
        self._create(client)

        client.save({CONANFILE: lib_conanfile,
                     "profile.txt": profile}, clean_first=True)

        client.run("build . --profile ./profile.txt --build missing")
        self.assertIn("Hello World!", client.out)

    def test_build_mode_requires(self):
        client = TestClient()
        self._create(client)

        client.save({CONANFILE: lib_conanfile,
                     "profile.txt": profile}, clean_first=True)

        client.run("install . --profile ./profile.txt", assert_error=True)
        self.assertIn("ERROR: Missing prebuilt package for 'tool/0.1@lasote/stable'", client.out)
        client.run("install . --profile ./profile.txt --build=Pythontool", assert_error=True)
        self.assertIn("ERROR: Missing prebuilt package for 'tool/0.1@lasote/stable'", client.out)
        client.run("install . --profile ./profile.txt --build=tool/0.1*")
        self.assertIn("tool/0.1@lasote/stable: Created package", client.out)

        # now remove packages, ensure --build=missing also creates them
        client.run('remove "*:*" -c')
        client.run("install . --profile ./profile.txt --build=missing")
        self.assertIn("tool/0.1@lasote/stable: Created package", client.out)

    def test_profile_test_requires(self):
        client = TestClient()
        self._create(client)

        test_conanfile = """
import os
from conan import ConanFile, tools

class Testmylib(ConanFile):
    def requirements(self):
        self.requires(self.tested_reference_str)

    def build(self):
        self.run("mytool")

    def test(self):
        pass
        """
        client.save({CONANFILE: lib_conanfile,
                     "test_package/conanfile.py": test_conanfile,
                     "profile.txt": profile,
                     "profile2.txt": profile2}, clean_first=True)

        client.run("create . --user=lasote --channel=stable --profile ./profile.txt --build missing")
        self.assertEqual(2, str(client.out).splitlines().count("Hello World!"))

    def test_consumer_patterns(self):
        client = TestClient()
        self._create(client)

        test_conanfile = """
import os
from conan import ConanFile, tools

class Testmylib(ConanFile):

    def build(self):
        self.run("mytool")
    def test(self):
        pass
        """
        lib_conanfile = """
import os
from conan import ConanFile, tools

class mylib(ConanFile):
    name = "mylib"
    version = "0.1"


"""
        profile_patterns = """
[tool_requires]
&: tool/0.1@lasote/stable
nonexistingpattern*: sometool/1.2@user/channel
"""
        client.save({CONANFILE: lib_conanfile,
                     "test_package/conanfile.py": test_conanfile,
                     "profile.txt": profile_patterns}, clean_first=True)

        client.run("create . --user=lasote --channel=stable --profile=./profile.txt --build=missing")
        self.assertEqual(1, str(client.out).splitlines().count("Hello World!"))

    def test_build_requires_options(self):
        client = TestClient()
        client.save({CONANFILE: GenConanfile("mytool", "0.1")})
        client.run("export . --user=lasote --channel=stable")

        conanfile = """
from conan import ConanFile, tools

class mylib(ConanFile):
    name = "mylib"
    version = "0.1"
    build_requires = "mytool/0.1@lasote/stable"
    options = {"coverage": [True, False]}
    def build(self):
        self.output.info("Coverage %s" % self.options.coverage)
"""
        client.save({CONANFILE: conanfile}, clean_first=True)
        client.run("build . -o mylib*:coverage=True --build missing")
        client.assert_listed_require({"mytool/0.1@lasote/stable": "Cache"}, build=True)
        self.assertIn("conanfile.py (mylib/0.1): Coverage True", client.out)

        client.save({CONANFILE: conanfile}, clean_first=True)
        client.run("build . -o coverage=True")
        client.assert_listed_require({"mytool/0.1@lasote/stable": "Cache"}, build=True)
        self.assertIn("mytool/0.1@lasote/stable: Already installed!", client.out)
        self.assertIn("conanfile.py (mylib/0.1): Coverage True", client.out)


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
