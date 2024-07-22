import textwrap

from conan.test.utils.tools import TestClient


def test_settings_definitions():
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            settings = "os"
            def generate(self):
                definition = self.settings.possible_values()
                assert "os" in definition
                assert "compiler" not in definition
                assert "arch" not in definition
                self.output.info(", ".join(definition["os"]))
                ios = definition["os"]["iOS"]["version"]
                self.output.info(f"iOS: {ios}")

                os_definition = self.settings.os.possible_values()
                ios = os_definition["iOS"]["version"]
                self.output.info(f"iOS2: {ios}")
            """)
    c.save({"conanfile.py": conanfile})
    # New settings are there
    c.run("install . -s os=Linux")
    assert "conanfile.py: Windows, WindowsStore, WindowsCE, Linux," in c.out
    assert "conanfile.py: iOS: ['7.0', '7.1', '8.0'," in c.out
    assert "conanfile.py: iOS2: ['7.0', '7.1', '8.0'," in c.out


def test_settings_definitions_compiler():
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            settings = "compiler"
            def generate(self):
                definition = self.settings.compiler.version.possible_values()
                self.output.info("HOST: " + ", ".join(definition))
                definition = self.settings_build.compiler.version.possible_values()
                self.output.info("BUILD: " + ", ".join(definition))
                cppstds = self.settings.compiler.cppstd.possible_values()
                self.output.info("CPPSTDS: " + str(cppstds))
            """)
    profile = textwrap.dedent("""\
        [settings]
        compiler=msvc
        compiler.version=192
        compiler.runtime=dynamic
        """)
    c.save({"conanfile.py": conanfile,
            "profile": profile})
    # New settings are there
    c.run("install . -pr=profile -s:b compiler=gcc")
    assert "conanfile.py: HOST: 170, 180, 190, 191, 192" in c.out
    assert "conanfile.py: BUILD: 4.1, 4.4, 4.5, 4.6, 4.7," in c.out
    assert "conanfile.py: CPPSTDS: [None, '14', '17', '20', '23']" in c.out
