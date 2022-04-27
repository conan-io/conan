import textwrap

from conans.test.utils.tools import TestClient


def test_version():
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.scm import Version

        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            settings = "compiler"
            def configure(self):
                v = Version(self.settings.compiler.version)
                assert v > "10"
        """)
    c.save({"conanfile.py": conanfile})
    settings = "-s compiler=gcc -s compiler.libcxx=libstdc++11"
    c.run("create . {} -s compiler.version=11".format(settings))
    c.run("create . {} -s compiler.version=9".format(settings), assert_error=True)
