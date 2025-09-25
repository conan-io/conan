import os
import platform
import textwrap

import pytest

from conan.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
def test_autotools_universal_binary():
    """Test that AutotoolsToolchain works with universal binaries on macOS"""
    client = TestClient(path_with_spaces=False)

    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.gnu import AutotoolsToolchain, Autotools
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
                at_toolchain = AutotoolsToolchain(self)
                at_toolchain.generate()

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

    test_conanfile = textwrap.dedent("""
        import os

        from conan import ConanFile
        from conan.tools.gnu import AutotoolsToolchain, Autotools, AutotoolsDeps
        from conan.tools.layout import basic_layout
        from conan.tools.build import can_run


        class mylibraryTestConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "AutotoolsDeps", "AutotoolsToolchain"

            def requirements(self):
                self.requires(self.tested_reference_str)

            def build(self):
                autotools = Autotools(self)
                autotools.autoreconf()
                autotools.configure()
                autotools.make()

            def layout(self):
                basic_layout(self)

            def test(self):
                exe = os.path.join(self.cpp.build.bindir, "main")
                self.run(f"lipo {exe} -info", env="conanrun")
            """)


    client.run('new autotools_lib -d name=mylibrary -d version=0.1')

    client.save({"conanfile.py": conanfile, "test_package/conanfile.py": test_conanfile})

    # Test universal binary creation
    client.run('create . -s="arch=armv8|x86_64" -tf=""')

    # Verify the library contains both architectures
    assert "libmylibrary.a are: x86_64 arm64" in client.out

    client.run('test test_package mylibrary/1.0 -s="arch=armv8|x86_64"')

    assert "./main are: x86_64 arm64" in client.out
