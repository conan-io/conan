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
        c.run("graph explain --requires=lib/1.0 -pr windows")
        expected = textwrap.dedent("""\
            settings: Windows, Release
            options: shared=False
            diff
              explanation: This binary is an exact match for the defined inputs
            """)
        assert textwrap.indent(expected, "      ") in c.out
        c.run("graph explain --requires=lib/1.0 -pr windows --format=json")
        cache = json.loads(c.stdout)["closest_binaries"]
        revisions = cache["lib/1.0"]["revisions"]
        pkgs = revisions["5313a980ea0c56baeb582c510d6d9fbc"]["packages"]
        assert len(pkgs) == 1
        pkg1 = pkgs["3d714b452400b3c3d6a964f42d5ec5004a6f22dc"]
        assert pkg1["diff"]["platform"] == {}
        assert pkg1["diff"]["settings"] == {}
        assert pkg1["diff"]["options"] == {}
        assert pkg1["diff"]["dependencies"] == {}
        assert pkg1["diff"]["explanation"] == "This binary is an exact match for the defined inputs"

    def test_settings_exact_match_complete(self, client):
        # We find 2 exact matches for os=Windows shared=True
        c = client
        c.save({"windows": "[settings]\nos=Windows\n[options]\n*:shared=True"})
        c.run("graph explain --requires=lib/1.0 -pr windows")
        expected = textwrap.dedent("""\
            settings: Windows, Release
            options: shared=True
            diff
              explanation: This binary is an exact match for the defined inputs
            """)
        assert textwrap.indent(expected, "      ") in c.out
        c.run("graph explain --requires=lib/1.0 -pr windows --format=json")
        cache = json.loads(c.stdout)["closest_binaries"]
        revisions = cache["lib/1.0"]["revisions"]
        pkgs = revisions["5313a980ea0c56baeb582c510d6d9fbc"]["packages"]
        assert len(pkgs) == 1
        pkg1 = pkgs["c2dd2d51b5074bdb5b7d717929372de09830017b"]
        assert pkg1["diff"]["platform"] == {}
        assert pkg1["diff"]["settings"] == {}
        assert pkg1["diff"]["options"] == {}
        assert pkg1["diff"]["dependencies"] == {}
        assert pkg1["diff"]["explanation"] == "This binary is an exact match for the defined inputs"

    def test_different_option(self, client):
        # We find 1 closest match in Linux static
        c = client
        c.save({"linux": "[settings]\nos=Linux\n[options]\n*:shared=True"})
        c.run("graph explain --requires=lib/1.0 -pr linux")
        expected = textwrap.dedent("""\
            remote: Local Cache
            settings: Linux, Release
            options: shared=False
            diff
              options
                expected: shared=True
                existing: shared=False
              explanation: This binary was built with the same settings, but different options
            """)
        assert textwrap.indent(expected, "      ") in c.out
        c.run("graph explain --requires=lib/1.0 -pr linux --format=json")
        cache = json.loads(c.stdout)["closest_binaries"]
        revisions = cache["lib/1.0"]["revisions"]
        pkgs = revisions["5313a980ea0c56baeb582c510d6d9fbc"]["packages"]
        assert len(pkgs) == 1
        pkg1 = pkgs["499989797d9192081b8f16f7d797b107a2edd8da"]
        assert pkg1["diff"]["platform"] == {}
        assert pkg1["diff"]["settings"] == {}
        assert pkg1["diff"]["options"] == {'existing': ['shared=False'], 'expected': ['shared=True']}
        assert pkg1["diff"]["dependencies"] == {}
        assert pkg1["diff"]["explanation"] == "This binary was built with the same settings, " \
                                              "but different options"

    def test_different_setting(self, client):
        # We find 1 closest match in Linux static
        c = client
        c.save({"windows": "[settings]\nos=Windows\nbuild_type=Debug\n[options]\n*:shared=True"})
        c.run("graph explain --requires=lib/1.0 -pr windows")
        expected = textwrap.dedent("""\
            remote: Local Cache
            settings: Windows, Release
            options: shared=True
            diff
              settings
                expected: build_type=Debug
                existing: build_type=Release
              explanation: This binary was built with different settings.
            """)
        assert textwrap.indent(expected, "      ") in c.out
        c.run("graph explain --requires=lib/1.0 -pr windows --format=json")
        cache = json.loads(c.stdout)["closest_binaries"]
        revisions = cache["lib/1.0"]["revisions"]
        pkgs = revisions["5313a980ea0c56baeb582c510d6d9fbc"]["packages"]
        assert len(pkgs) == 1
        pkg1 = pkgs["c2dd2d51b5074bdb5b7d717929372de09830017b"]
        assert pkg1["diff"]["platform"] == {}
        assert pkg1["diff"]["settings"] == {'existing': ['build_type=Release'],
                                            'expected': ['build_type=Debug']}
        assert pkg1["diff"]["options"] == {}
        assert pkg1["diff"]["dependencies"] == {}
        assert pkg1["diff"]["explanation"] == "This binary was built with different settings."

    def test_different_platform(self, client):
        # We find closest match in other platforms
        c = client
        c.save({"macos": "[settings]\nos=Macos\nbuild_type=Release\n[options]\n*:shared=True"})
        c.run("graph explain --requires=lib/1.0 -pr macos")
        expected = textwrap.dedent("""\
            remote: Local Cache
            settings: Windows, Release
            options: shared=True
            diff
              platform
                expected: os=Macos
                existing: os=Windows
              explanation: This binary belongs to another OS or Architecture, highly incompatible.
            """)
        assert textwrap.indent(expected, "      ") in c.out
        c.run("graph explain --requires=lib/1.0 -pr macos --format=json")
        cache = json.loads(c.stdout)["closest_binaries"]
        revisions = cache["lib/1.0"]["revisions"]
        pkgs = revisions["5313a980ea0c56baeb582c510d6d9fbc"]["packages"]
        assert len(pkgs) == 1
        pkg1 = pkgs["c2dd2d51b5074bdb5b7d717929372de09830017b"]
        assert pkg1["diff"]["platform"] == {'existing': ['os=Windows'], 'expected': ['os=Macos']}
        assert pkg1["diff"]["settings"] == {}
        assert pkg1["diff"]["options"] == {}
        assert pkg1["diff"]["dependencies"] == {}
        assert pkg1["diff"]["explanation"] == "This binary belongs to another OS or Architecture, " \
                                              "highly incompatible."

    def test_different_conf(self, client):
        # We find closest match in other platforms
        c = client
        c.save_home({"global.conf": "tools.info.package_id:confs=['user.foo:bar']"})
        c.run("graph explain --requires=lib/1.0 -c user.foo:bar=42 -s os=Linux")
        expected = textwrap.dedent("""\
            remote: Local Cache
            settings: Linux, Release
            options: shared=False
            diff
              confs
                expected: user.foo:bar=42
                existing: user.foo:bar=None
              explanation: This binary has same settings, options and dependencies, but different confs
            """)
        assert textwrap.indent(expected, "      ") in c.out
        c.run("graph explain --requires=lib/1.0 -pr macos --format=json")
        cache = json.loads(c.stdout)["closest_binaries"]
        revisions = cache["lib/1.0"]["revisions"]
        pkgs = revisions["5313a980ea0c56baeb582c510d6d9fbc"]["packages"]
        assert len(pkgs) == 1
        pkg1 = pkgs["c2dd2d51b5074bdb5b7d717929372de09830017b"]
        assert pkg1["diff"]["platform"] == {'existing': ['os=Windows'], 'expected': ['os=Macos']}
        assert pkg1["diff"]["settings"] == {}
        assert pkg1["diff"]["options"] == {}
        assert pkg1["diff"]["dependencies"] == {}
        assert pkg1["diff"]["explanation"] == "This binary belongs to another OS or Architecture, " \
                                              "highly incompatible."

    def test_different_python_requires(self):
        c = TestClient(light=True)
        c.save({"tool/conanfile.py": GenConanfile("tool"),
                "lib/conanfile.py": GenConanfile("lib", "1.0")
               .with_python_requires("tool/[>=1.0]")})
        c.run("create tool --version=1.0 -s os=Linux")
        c.run("create lib -s os=Linux")
        c.run("create tool --version=2.0 -s os=Linux")
        c.run("graph explain --requires=lib/1.0 -s os=Linux")
        expected = textwrap.dedent("""\
            remote: Local Cache
            python_requires: tool/1.0.Z
            diff
              python_requires
                expected: tool/2.0.Z
                existing: tool/1.0.Z
              explanation: This binary has same settings, options and dependencies, but different python_requires
            """)
        assert textwrap.indent(expected, "      ") in c.out
        c.run("graph explain --requires=lib/1.0 -s os=Linux --format=json")
        cache = json.loads(c.stdout)["closest_binaries"]
        revisions = cache["lib/1.0"]["revisions"]
        pkgs = revisions["5313a980ea0c56baeb582c510d6d9fbc"]["packages"]
        assert len(pkgs) == 1
        pkg1 = pkgs["c2dd2d51b5074bdb5b7d717929372de09830017b"]
        assert pkg1["diff"]["platform"] == {'existing': ['os=Windows'], 'expected': ['os=Macos']}
        assert pkg1["diff"]["settings"] == {}
        assert pkg1["diff"]["options"] == {}
        assert pkg1["diff"]["dependencies"] == {}
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
        c.run("graph explain --requires=lib/1.0 --missing=lib/1.0 -s os=Windows")
        expected = textwrap.dedent("""\
            settings: Linux
            requires: dep/1.Y.Z
            diff
              platform
                expected: os=Windows
                existing: os=Linux
              dependencies
                expected: dep/2.Y.Z
                existing: dep/1.Y.Z
              explanation: This binary belongs to another OS or Architecture, highly incompatible.
            """)
        assert textwrap.indent(expected, "      ") in c.out

    def test_other_dependencies(self, client):
        c = client
        c.run("install --requires=lib/1.0 -s os=Linux", assert_error=True)
        assert "ERROR: Missing prebuilt package for 'lib/1.0'" in c.out
        c.run("graph explain --requires=lib/1.0 -s os=Linux")
        expected = textwrap.dedent("""\
            settings: Linux
            requires: dep/1.Y.Z
            diff
              dependencies
                expected: dep/2.Y.Z
                existing: dep/1.Y.Z
              explanation: This binary has same settings and options, but different dependencies
               """)
        assert textwrap.indent(expected, "      ") in c.out


def test_change_in_package_type():
    tc = TestClient(light=True)
    tc.save({
        "libc/conanfile.py": GenConanfile("libc", "1.0"),
        "libb/conanfile.py": GenConanfile("libb", "1.0")
        .with_requires("libc/1.0"),
        "liba/conanfile.py": GenConanfile("liba", "1.0")
        .with_requires("libb/1.0")
    })

    tc.run("create libc")
    tc.run("create libb")
    tc.run("create liba")

    tc.save({
        "libc/conanfile.py": GenConanfile("libc", "1.0")
        .with_package_type("application")
    })
    tc.run("create libc")

    tc.run("create liba", assert_error=True)
    assert "Missing binary: libb/1.0" in tc.out

    tc.run("graph explain --requires=liba/1.0")
    # This fails, graph explain thinks everything is ok
    assert "explanation: This binary is an exact match for the defined inputs" not in tc.out


def test_conf_difference_shown():
    tc = TestClient(light=True)
    tc.save({
        "libc/conanfile.py": GenConanfile("libc", "1.0"),
        "libb/conanfile.py": GenConanfile("libb", "1.0")
        .with_requires("libc/1.0"),
        "liba/conanfile.py": GenConanfile("liba", "1.0")
        .with_requires("libb/1.0")
    })
    tc.save_home({"global.conf": "tools.info.package_id:confs=['user.foo:bar']"})

    tc.run("create libc")
    tc.run("create libb")
    tc.run("create liba")

    tc.run("remove libc/*:* -c")

    tc.run("create libc -c user.foo:bar=42")

    tc.run("create liba", assert_error=True)
    assert "Missing prebuilt package for 'libc/1.0'" in tc.out

    tc.run("graph explain --requires=liba/1.0")
    assert "conf: user.foo:bar=42" in tc.out


class TestDistance:
    def test_multiple_distance_ordering(self):
        tc = TestClient()
        tc.save({
            "conanfile.py": GenConanfile("pkg", "1.0").with_requires("dep/1.0"),
            "dep/conanfile.py": GenConanfile("dep", "1.0")
            .with_option("shared", [True, False])
            .with_option("fPIC", [True, False])})

        tc.run("create dep -o shared=True -o fPIC=True")
        tc.run("create dep -o shared=True -o fPIC=False")

        tc.run('graph explain . -o *:shared=False -o *:fPIC=False')
        # We don't expect the further binary to show
        assert "a657a8fc96dd855e2a1c90a9fe80125f0c4635a0" not in tc.out
        # We expect the closer binary to show
        assert "a6923b987deb1469815dda84aab36ac34f370c48" in tc.out
