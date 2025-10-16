import textwrap

from parameterized import parameterized

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


@parameterized.expand(["AutotoolsToolchain", "MesonToolchain", "BazelToolchain"])
def test_create_universal_binary(toolchain):
    client = TestClient()
    conanfile = (GenConanfile().with_settings("os", "arch", "compiler", "build_type")
                 .with_generator(toolchain))
    client.save({"conanfile.py": conanfile})

    client.run('create . --name=foo --version=1.0 -s="arch=armv8|armv8.3|x86_64"',
               assert_error=True)
    assert (f"Error in generator '{toolchain}': "
            f"Universal binaries not supported by toolchain.") in client.out


def test_create_universal_binary_test_package_folder():
    # https://github.com/conan-io/conan/issues/18820
    # While multi-arch is Darwin specific, this was a cmake_layout issue, so it can be
    # tested in any platform
    c = TestClient()
    test_conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import cmake_layout

        class mylibraryTestConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"

            def requirements(self):
                self.requires(self.tested_reference_str)

            def layout(self):
                cmake_layout(self)

            def test(self):
                pass
            """)
    c.save({"conanfile.py": GenConanfile("pkg", "0.1").with_settings("arch"),
            "test_package/conanfile.py": test_conanfile})

    c.run('create . -s="arch=armv8|x86_64"')
    c.run("list *:*")
    assert "arch: armv8|x86_64" in c.out
