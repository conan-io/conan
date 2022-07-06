import textwrap

from conans.test.utils.tools import TestClient


def test_basic_validate_build_test():

    t = TestClient()
    conanfile = textwrap.dedent("""
    from conan import ConanFile
    from conans.errors import ConanInvalidConfiguration

    class myConan(ConanFile):
        name = "foo"
        version = "1.0"
        settings = "os", "arch", "compiler"

        def validate_build(self):
            if self.settings.compiler == "gcc":
                raise ConanInvalidConfiguration("This doesn't build in GCC")

        def package_id(self):
            del self.info.settings.compiler
    """)

    settings_gcc = "-s compiler=gcc -s compiler.libcxx=libstdc++11 -s compiler.version=11"
    settings_clang = "-s compiler=clang -s compiler.libcxx=libc++ -s compiler.version=8"

    t.save({"conanfile.py": conanfile})
    t.run(f"create . {settings_gcc}", assert_error=True)

    assert "This doesn't build in GCC" in t.out

    t.run(f"create . {settings_clang}")

    # Now with GCC again, but now we have the binary, we don't need to build, so it doesn't fail
    t.run(f"create . {settings_gcc} --build missing")
    assert "foo/1.0: Already installed!" in t.out

    # But if I force the build... it will fail
    t.run(f"create . {settings_gcc} ", assert_error=True)
    assert "This doesn't build in GCC" in t.out
