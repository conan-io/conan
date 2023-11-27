import json
import textwrap

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


class TestFilterProfile:
    @pytest.fixture(scope="class")
    def client(self):
        c = TestClient()
        c.save({"lib/conanfile.py": GenConanfile("lib", "1.0").with_settings("os", "build_type")
                                                              .with_shared_option()})
        c.run("create lib -s os=Linux")
        c.run("create lib -s os=Windows")
        c.run("create lib -s os=Windows -o *:shared=True")
        return c

    def test_settings_exact_match_incomplete(self, client):
        # We find 2 exact matches for os=Windows
        c = client
        c.save({"windows": "[settings]\nos=Windows"})
        c.run("graph find-binaries --requires=lib/1.0 -pr windows")
        expected = textwrap.dedent("""\
            settings: Windows, Release
            options: shared=False
            diff
              explanation: This binary is an exact match for the defined inputs
            """)
        assert textwrap.indent(expected, "        ") in c.out
        c.run("graph find-binaries --requires=lib/1.0 -pr windows --format=json")
        cache = json.loads(c.stdout)["Closest binaries"]
        revisions = cache["lib/1.0"]["revisions"]
        pkgs = revisions["5313a980ea0c56baeb582c510d6d9fbc"]["packages"]
        assert len(pkgs) == 1
        pkg1 = pkgs["3d714b452400b3c3d6a964f42d5ec5004a6f22dc"]
        assert pkg1["diff"]["platform"] == {}
        assert pkg1["diff"]["settings"] == {}
        assert pkg1["diff"]["options"] == {}
        assert pkg1["diff"]["dependencies"] == []
        assert pkg1["diff"]["explanation"] == "This binary is an exact match for the defined inputs"

    def test_settings_exact_match_complete(self, client):
        # We find 2 exact matches for os=Windows shared=True
        c = client
        c.save({"windows": "[settings]\nos=Windows\n[options]\n*:shared=True"})
        c.run("graph find-binaries --requires=lib/1.0 -pr windows")
        expected = textwrap.dedent("""\
            settings: Windows, Release
            options: shared=True
            diff
              explanation: This binary is an exact match for the defined inputs
            """)
        assert textwrap.indent(expected, "        ") in c.out
        c.run("graph find-binaries --requires=lib/1.0 -pr windows --format=json")
        cache = json.loads(c.stdout)["Closest binaries"]
        revisions = cache["lib/1.0"]["revisions"]
        pkgs = revisions["5313a980ea0c56baeb582c510d6d9fbc"]["packages"]
        assert len(pkgs) == 1
        pkg1 = pkgs["c2dd2d51b5074bdb5b7d717929372de09830017b"]
        assert pkg1["diff"]["platform"] == {}
        assert pkg1["diff"]["settings"] == {}
        assert pkg1["diff"]["options"] == {}
        assert pkg1["diff"]["dependencies"] == []
        assert pkg1["diff"]["explanation"] == "This binary is an exact match for the defined inputs"

    def test_different_option(self, client):
        # We find 1 closest match in Linux static
        c = client
        c.save({"linux": "[settings]\nos=Linux\n[options]\n*:shared=True"})
        c.run("graph find-binaries --requires=lib/1.0 -pr linux")
        expected = textwrap.dedent("""\
            settings: Linux, Release
            options: shared=False
            diff
              options: shared=True
              explanation: This binary was built with the same settings, but different options
            """)
        assert textwrap.indent(expected, "        ") in c.out
        c.run("graph find-binaries --requires=lib/1.0 -pr linux --format=json")
        cache = json.loads(c.stdout)["Closest binaries"]
        revisions = cache["lib/1.0"]["revisions"]
        pkgs = revisions["5313a980ea0c56baeb582c510d6d9fbc"]["packages"]
        assert len(pkgs) == 1
        pkg1 = pkgs["499989797d9192081b8f16f7d797b107a2edd8da"]
        assert pkg1["diff"]["platform"] == {}
        assert pkg1["diff"]["settings"] == {}
        assert pkg1["diff"]["options"] == {"shared": "True"}
        assert pkg1["diff"]["dependencies"] == []
        assert pkg1["diff"]["explanation"] == "This binary was built with the same settings, " \
                                              "but different options"

    def test_different_setting(self, client):
        # We find 1 closest match in Linux static
        c = client
        c.save({"windows": "[settings]\nos=Windows\nbuild_type=Debug\n[options]\n*:shared=True"})
        c.run("graph find-binaries --requires=lib/1.0 -pr windows")
        expected = textwrap.dedent("""\
            settings: Windows, Release
            options: shared=True
            diff
              settings: Debug
              explanation: This binary was built with different settings (compiler, build_type).
            """)
        assert textwrap.indent(expected, "        ") in c.out
        c.run("graph find-binaries --requires=lib/1.0 -pr windows --format=json")
        cache = json.loads(c.stdout)["Closest binaries"]
        revisions = cache["lib/1.0"]["revisions"]
        pkgs = revisions["5313a980ea0c56baeb582c510d6d9fbc"]["packages"]
        assert len(pkgs) == 1
        pkg1 = pkgs["c2dd2d51b5074bdb5b7d717929372de09830017b"]
        assert pkg1["diff"]["platform"] == {}
        assert pkg1["diff"]["settings"] == {"build_type": "Debug"}
        assert pkg1["diff"]["options"] == {}
        assert pkg1["diff"]["dependencies"] == []
        assert pkg1["diff"]["explanation"] == "This binary was built with different settings " \
                                              "(compiler, build_type)."

    def test_different_platform(self, client):
        # We find closest match in other platforms
        c = client
        c.save({"macos": "[settings]\nos=Macos\nbuild_type=Release\n[options]\n*:shared=True"})
        c.run("graph find-binaries --requires=lib/1.0 -pr macos")
        expected = textwrap.dedent("""\
            settings: Windows, Release
            options: shared=True
            diff
              platform: os=Macos
              explanation: This binary belongs to another OS or Architecture, highly incompatible.
            """)
        assert textwrap.indent(expected, "        ") in c.out
        c.run("graph find-binaries --requires=lib/1.0 -pr macos --format=json")
        cache = json.loads(c.stdout)["Closest binaries"]
        revisions = cache["lib/1.0"]["revisions"]
        pkgs = revisions["5313a980ea0c56baeb582c510d6d9fbc"]["packages"]
        assert len(pkgs) == 1
        pkg1 = pkgs["c2dd2d51b5074bdb5b7d717929372de09830017b"]
        assert pkg1["diff"]["platform"] == {"os": "Macos"}
        assert pkg1["diff"]["settings"] == {}
        assert pkg1["diff"]["options"] == {}
        assert pkg1["diff"]["dependencies"] == []
        assert pkg1["diff"]["explanation"] == "This binary belongs to another OS or Architecture, " \
                                              "highly incompatible."


class TestMissingBinaryDeps:
    @pytest.fixture(scope="class")
    def client(self):
        c = TestClient()
        c.save({"dep/conanfile.py": GenConanfile("dep").with_settings("os"),
                "lib/conanfile.py": GenConanfile("lib", "1.0").with_settings("os")
                                                              .with_requires("dep/[>=1.0]")})
        c.run("create dep --version=1.0 -s os=Linux")
        c.run("create lib -s os=Linux")
        c.run("create dep --version=2.0 -s os=Linux")
        return c

    def test_other_platform(self, client):
        c = client
        c.run("install --requires=lib/1.0 -s os=Windows", assert_error=True)
        assert "ERROR: Missing prebuilt package for 'dep/2.0', 'lib/1.0'" in c.out
        # We use the --missing=lib/1.0 to specify we want this binary and not dep/2.0
        c.run("graph find-binaries --requires=lib/1.0 --missing=lib/1.0 -s os=Windows")
        expected = textwrap.dedent("""\
            settings: Linux
            requires: dep/1.Y.Z
            diff
              platform: os=Windows
              dependencies: dep/2.Y.Z
              explanation: This binary belongs to another OS or Architecture, highly incompatible.
            """)
        assert textwrap.indent(expected, "        ") in c.out

    def test_other_dependencies(self, client):
        c = client
        c.run("install --requires=lib/1.0 -s os=Linux", assert_error=True)
        assert "ERROR: Missing prebuilt package for 'lib/1.0'" in c.out
        c.run("graph find-binaries --requires=lib/1.0 -s os=Linux")
        expected = textwrap.dedent("""\
            settings: Linux
            requires: dep/1.Y.Z
            diff
              dependencies: dep/2.Y.Z
              explanation: This binary has same settings and options, but different dependencies
               """)
        assert textwrap.indent(expected, "        ") in c.out
