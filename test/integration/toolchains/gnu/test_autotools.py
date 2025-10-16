import textwrap

from conan.test.utils.tools import TestClient


def test_autotools_make_parameters():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.gnu import AutotoolsToolchain, Autotools

        class Conan(ConanFile):
            settings = "os"
            generators = "AutotoolsDeps", "AutotoolsToolchain", "VirtualRunEnv"

            def run(self, cmd, *args, **kwargs):
                self.output.info(f"Running {cmd}")

            def build(self):
                autotools = Autotools(self)
                autotools.make(makefile="MyMake", target="test", args=["-j4", "VERBOSE=1"])
                autotools.install(makefile="OtherMake")
        """)

    client.save({"conanfile.py": conanfile})
    client.run("build .")
    assert "make --file=MyMake test -j4 VERBOSE=1" in client.out
    assert "make --file=OtherMake install" in client.out
