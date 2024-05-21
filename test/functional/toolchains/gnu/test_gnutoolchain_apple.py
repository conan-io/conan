import os
import platform
import textwrap

import pytest

from conan.tools.apple.apple import _to_apple_arch
from conan.test.assets.autotools import gen_makefile
from conan.test.assets.sources import gen_function_h, gen_function_cpp
from conan.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
@pytest.mark.parametrize("config", [("x86_64", "Macos", "10.14", None),
                                    ("armv8", "iOS", "10.0", "iphoneos"),
                                    ("armv7", "iOS", "10.0", "iphoneos"),
                                    ("x86", "iOS", "10.0", "iphonesimulator"),
                                    ("x86_64", "iOS", "10.0", "iphonesimulator"),
                                    ("armv8", "Macos", "10.14", None)  # M1
                                    ])
def test_makefile_arch(config):
    makefile = gen_makefile(apps=["app"], libs=["hello"])
    conanfile_py = textwrap.dedent("""
        from conan import ConanFile, tools
        from conan.tools.gnu import Autotools

        class App(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            options = {"shared": [True, False], "fPIC": [True, False]}
            default_options = {"shared": False, "fPIC": True}
            generators = "GnuToolchain"

            def config_options(self):
                if self.settings.os == "Windows":
                    self.options.rm_safe("fPIC")

            def configure(self):
                if self.options.shared:
                    self.options.rm_safe("fPIC")

            def build(self):
                env_build = Autotools(self)
                env_build.make()
    """)
    arch, os_, os_version, os_sdk = config
    profile = textwrap.dedent("""
                include(default)
                [settings]
                os = {os}
                {os_sdk}
                os.version = {os_version}
                arch = {arch}
                """).format(os=os_, arch=arch,
                            os_version=os_version, os_sdk="os.sdk = " + os_sdk if os_sdk else "")

    t = TestClient()
    hello_h = gen_function_h(name="hello")
    hello_cpp = gen_function_cpp(name="hello")
    main_cpp = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])

    t.save({"Makefile": makefile,
            "hello.h": hello_h,
            "hello.cpp": hello_cpp,
            "app.cpp": main_cpp,
            "conanfile.py": conanfile_py,
            "profile": profile})

    t.run("install . --profile:host=profile --profile:build=default")
    t.run("build . --profile:host=profile --profile:build=default")

    libhello = os.path.join(t.current_folder, "libhello.a")
    app = os.path.join(t.current_folder, "app")
    assert os.path.isfile(libhello)
    assert os.path.isfile(app)

    expected_arch = _to_apple_arch(arch)
    t.run_command('lipo -info "%s"' % libhello)
    assert "architecture: %s" % expected_arch in t.out

    t.run_command('lipo -info "%s"' % app)
    assert "architecture: %s" % expected_arch in t.out
