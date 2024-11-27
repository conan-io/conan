import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_lockfile_compatibility():
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "pkg"
            version = "1.0"
            settings = "build_type"
            def compatibility(self):
                if self.settings.build_type == "Release":
                    return [ {"settings": [("build_type", None)]}, ]
            """)
    c.save({"conanfile.py": conanfile,
            "profile": ""})
    c.run("create . -pr=profile")
    c.save({"conanfile.py": GenConanfile().with_requires("pkg/1.0")})
    c.run("install .")
    assert "pkg/1.0: Main binary package 'efa83b160a55b033c4ea706ddb980cd708e3ba1b' missing" in c.out
    assert "Found compatible package 'da39a3ee5e6b4b0d3255bfef95601890afd80709'" in c.out

    c.run("lock create conanfile.py")
    assert "pkg/1.0: Main binary package 'efa83b160a55b033c4ea706ddb980cd708e3ba1b' missing" in c.out
    assert "Found compatible package 'da39a3ee5e6b4b0d3255bfef95601890afd80709'" in c.out

    c.run("lock create conanfile.py --lockfile=conan.lock")
    assert "pkg/1.0: Main binary package 'efa83b160a55b033c4ea706ddb980cd708e3ba1b' missing" in c.out
    assert "Found compatible package 'da39a3ee5e6b4b0d3255bfef95601890afd80709'" in c.out

    c.run("install . --lockfile=conan.lock")
    c.assert_listed_binary({"pkg/1.0": ("da39a3ee5e6b4b0d3255bfef95601890afd80709", "Cache")})
