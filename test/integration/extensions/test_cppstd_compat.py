import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_compatible_cppstd():
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            settings = "os", "compiler"

            def package_info(self):
                self.output.info("PackageInfo!: Cppstd version: %s!"
                                 % self.settings.compiler.cppstd)
        """)
    profile = textwrap.dedent("""
        [settings]
        os = Linux
        compiler=gcc
        compiler.version=12
        compiler.libcxx=libstdc++
        """)
    c.save({"conanfile.py": conanfile,
            "myprofile": profile})
    # Create package with cppstd 17
    c.run("create .  -pr=myprofile -s compiler.cppstd=17")
    package_id = "95dcfeb51c04968b4ee960ee393cf2c1ebcf7782"
    assert f"pkg/0.1: Package '{package_id}' created" in c.out

    # package can be used with a profile gcc cppstd20 falling back to 17
    c.save({"conanfile.py": GenConanfile().with_require("pkg/0.1")})
    c.run("install . -pr=myprofile -s compiler.cppstd=20")
    assert f"Using compatible package '{package_id}'"
    assert "pkg/0.1: PackageInfo!: Cppstd version: 17!" in c.out
    c.assert_listed_binary({"pkg/0.1": (f"{package_id}", "Cache")})
    assert "pkg/0.1: Already installed!" in c.out


def test_compatible_cppstd_missing_compiler():
    c = TestClient()
    settings_user = textwrap.dedent("""
    compiler:
        mycompiler:
            version: ["12"]
            libcxx: ["libstdc++"]
            cppstd: [15, 17, 20]
    """)
    conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"
                settings = "os", "compiler"

                def package_info(self):
                    self.output.info("PackageInfo!: Cppstd version: %s!"
                                     % self.settings.compiler.cppstd)
            """)
    profile = textwrap.dedent("""
            [settings]
            os = Linux
            compiler=mycompiler
            compiler.version=12
            compiler.libcxx=libstdc++
            """)
    c.save({"conanfile.py": conanfile,
            "myprofile": profile})
    c.save_home({"settings_user.yml": settings_user})
    # Create package with cppstd 17
    c.run("create .  -pr=myprofile -s compiler.cppstd=17")
    package_id = "51a90090adb1cbd330a64b4c3b3b32af809af4f9"
    assert f"pkg/0.1: Package '{package_id}' created" in c.out

    # package can't be used with cppstd 20 and fallback to 17, because mycompiler is not known
    # to the default cppstd_compat function. Ensure that it does not break and warns the user
    c.save({"conanfile.py": GenConanfile().with_require("pkg/0.1")})
    c.run("install . -pr=myprofile -s compiler.cppstd=20", assert_error=True)
    assert "Missing binary: pkg/0.1:b4b07859713551e8aac612f8080888c58b4711ae" in c.out
    assert 'pkg/0.1: WARN: No cppstd compatibility defined for compiler "mycompiler"' in c.out
