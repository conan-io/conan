import textwrap

from conans.test.utils.tools import TestClient


def test_settings_not_defined_consuming():
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "pkg"
            version = "1.0"
            settings = "os", "arch"

            def build(self):
                self.output.info(f"Building with os={self.settings.os}")
                self.output.info(f"Building with arch={self.settings.arch}")

            def package_id(self):
                del self.info.settings.os
                del self.info.settings.arch
        """)
    c.save({"conanfile.py": conanfile,
            "profile": ""})
    c.run("create . -pr=profile -s os=Windows -s arch=armv8")
    assert "Building with os=Windows" in c.out
    assert "Building with arch=armv8" in c.out
    c.run("install --requires=pkg/1.0 -pr=profile")
    # It doesn't fail, even if settings not defined
    c.run("install --requires=pkg/1.0 -pr=profile -s os=Linux -s arch=x86")
    # It doesn't fail, even if settings different value
