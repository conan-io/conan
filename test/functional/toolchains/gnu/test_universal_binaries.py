import platform
import textwrap

import pytest

from conan.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
def test_gnutoolchain_universal_binary():
    client = TestClient(path_with_spaces=False)

    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.gnu import GnuToolchain, Autotools
        from conan.tools.layout import basic_layout

        class mylibraryRecipe(ConanFile):
            name = "mylibrary"
            version = "1.0"
            package_type = "library"
            settings = "os", "compiler", "build_type", "arch"
            options = {"shared": [True, False], "fPIC": [True, False]}
            default_options = {"shared": False, "fPIC": True}

            exports_sources = "configure.ac", "Makefile.am", "src/*"

            def config_options(self):
                if self.settings.os == "Windows":
                    self.options.rm_safe("fPIC")

            def configure(self):
                if self.options.shared:
                    self.options.rm_safe("fPIC")

            def layout(self):
                basic_layout(self)

            def generate(self):
                gnu_toolchain = GnuToolchain(self)
                gnu_toolchain.generate()

            def build(self):
                autotools = Autotools(self)
                autotools.autoreconf()
                autotools.configure()
                autotools.make()

            def package(self):
                autotools = Autotools(self)
                autotools.install()
                self.run(f"lipo -info {os.path.join(self.package_folder, 'lib', 'libmylibrary.a')}")

            def package_info(self):
                self.cpp_info.libs = ["mylibrary"]

    """)

    client.run('new autotools_lib -d name=mylibrary -d version=0.1')

    client.save({"conanfile.py": conanfile})

    client.run('create . -s="arch=armv8|x86_64" -tf=""')

    assert "libmylibrary.a are: x86_64 arm64" in client.out
