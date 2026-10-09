import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_libc_settings_definitions():
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            settings = "os"
            def generate(self):
                definition = self.settings.os.possible_values()["Linux"]["libc"]
                self.output.info(f"LIBC: {list(definition)}")
                self.output.info(f"GLIBC: {definition['glibc']['version']}")
                self.output.info(f"MUSL: {definition['musl']['version']}")
                self.output.info(f"VALUE: {self.settings.get_safe('os.libc')} "
                                 f"{self.settings.get_safe('os.libc.version')}")
            """)
    c.save({"conanfile.py": conanfile})
    c.run("install . -s os=Linux -s os.libc=glibc -s os.libc.version=2.28")
    assert "LIBC: [None, 'glibc', 'musl']" in c.out
    assert "GLIBC: [None, '2.9', '2.10'," in c.out
    assert "MUSL: [None, '1.2.2', '1.2.3'," in c.out
    assert "VALUE: glibc 2.28" in c.out


def test_libc_settings_invalid():
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("pkg", "0.1").with_settings("os")})
    c.run("create . -s os=Linux -s os.libc=uclibc", assert_error=True)
    assert "Invalid setting 'uclibc' is not a valid 'settings.os.libc' value" in c.out
    c.run("create . -s os=Linux -s os.libc=musl -s os.libc.version=2.28", assert_error=True)
    assert "Invalid setting '2.28' is not a valid 'settings.os.libc.version' value" in c.out
    c.run("create . -s os=Windows -s os.libc=glibc", assert_error=True)
    assert "'settings.os.libc' doesn't exist for 'Windows'" in c.out


def test_libc_settings_package_id():
    """ An undefined libc must not change the package_id, so existing binaries remain valid
    """
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("pkg", "0.1").with_settings("os")})
    c.run("create . -s os=Linux")
    c.assert_listed_binary({"pkg/0.1": ("9a4eb3c8701508aa9458b1a73d0633783ecc2270", "Build")})
    c.run("create . -s os=Linux -s os.libc=glibc")
    c.assert_listed_binary({"pkg/0.1": ("42daf913e9f97f11b6c13db521d57da7800096ed", "Build")})
    c.run("create . -s os=Linux -s os.libc=glibc -s os.libc.version=2.28")
    c.assert_listed_binary({"pkg/0.1": ("62f5bc75c3689ca617f532937a352db395dbea59", "Build")})
