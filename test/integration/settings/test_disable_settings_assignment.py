import textwrap

from conan.test.utils.tools import TestClient


def test_disable_settings_assignment():
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            settings = "os"
            def generate(self):
                self.settings.os = "FreeBSD"
            """)
    c.save({"conanfile.py": conanfile})
    c.run("install .", assert_error=True)
    assert "Tried to define 'os' setting inside recipe" in c.out
