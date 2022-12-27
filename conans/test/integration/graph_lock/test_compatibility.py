import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


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
                   return [ {"settings": [("build_type", "None")]}, ]
            """)
    c.save({"conanfile.py": conanfile,
            "profile": ""})
    c.run("create . -pr=profile")
    c.save({"conanfile.py": GenConanfile().with_requires("pkg/1.0")})
    c.run("install .")
    assert "pkg/1.0: Main binary package '4024617540c4f240a6a5e8911b0de9ef38a11a72' missing. " \
           "Using compatible package '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9'" in c.out

    c.run("lock create conanfile.py --base")
    assert "pkg/1.0: Main binary package '4024617540c4f240a6a5e8911b0de9ef38a11a72' missing. " \
           "Using compatible package '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9'" in c.out

    c.run("lock create conanfile.py --lockfile=conan.lock")
    conan_lock = c.load("conan.lock")
    assert '"package_id": "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"' in conan_lock
    assert "pkg/1.0: Main binary package '4024617540c4f240a6a5e8911b0de9ef38a11a72' missing. " \
           "Using compatible package '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9'" in c.out

    c.run("install . --lockfile=conan.lock")
    assert "pkg/1.0:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache" in c.out
