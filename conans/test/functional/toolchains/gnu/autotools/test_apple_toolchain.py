import os
import textwrap
import platform

import pytest

from conans.client.tools.apple import to_apple_arch
from conans.test.assets.autotools import gen_makefile
from conans.test.assets.sources import gen_function_h, gen_function_cpp
from conans.test.utils.tools import TestClient

makefile = gen_makefile(apps=["app"], libs=["hello"])

conanfile_py = textwrap.dedent("""
    from conans import ConanFile, tools
    from conan.tools.gnu import Autotools

    class App(ConanFile):
        settings = "os", "arch", "compiler", "build_type"
        options = {"shared": [True, False], "fPIC": [True, False]}
        default_options = {"shared": False, "fPIC": True}
        generators = "AutotoolsToolchain"

        def config_options(self):
            if self.settings.os == "Windows":
                del self.options.fPIC

        def build(self):
            env_build = Autotools(self)
            env_build.make()
    """)


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
@pytest.mark.parametrize("config", [("x86_64", "Macos", "10.14"),
                                    ("armv8", "iOS", "10.0"),
                                    ("armv7", "iOS", "10.0"),
                                    ("x86", "iOS", "10.0"),
                                    ("x86_64", "iOS", "10.0"),
                                    ("armv8", "Macos", "10.14")  # M1
                                    ])
def test_makefile_arch(config):
    arch, os_, os_version = config
    profile = textwrap.dedent("""
                include(default)
                [settings]
                os = {os}
                os.version = {os_version}
                arch = {arch}
                """).format(os=os_, arch=arch, os_version=os_version)

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
    t.run("build .")

    libhello = os.path.join(t.current_folder, "libhello.a")
    app = os.path.join(t.current_folder, "app")
    assert os.path.isfile(libhello)
    assert os.path.isfile(app)

    expected_arch = to_apple_arch(arch)

    t.run_command('lipo -info "%s"' % libhello)
    assert "architecture: %s" % expected_arch in t.out

    t.run_command('lipo -info "%s"' % app)
    assert "architecture: %s" % expected_arch in t.out


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
@pytest.mark.parametrize("arch", ["x86_64", "armv8"])
def test_catalyst(arch):
    profile = textwrap.dedent("""
        include(default)
        [settings]
        os = Macos
        os.version = 13.0
        os.sdk = macosx
        os.subsystem = catalyst
        os.subsystem.ios_version = 13.1
        arch = {arch}
        """).format(arch=arch)

    t = TestClient()
    hello_h = gen_function_h(name="hello")
    hello_cpp = gen_function_cpp(name="hello")
    main_cpp = textwrap.dedent("""
        #include "hello.h"
        #include <TargetConditionals.h>
        #include <iostream>

        int main()
        {
        #if TARGET_OS_MACCATALYST
            std::cout << "running catalyst " << __IPHONE_OS_VERSION_MIN_REQUIRED << std::endl;
        #else
            #error "not building for Apple Catalyst"
        #endif
        }
        """)

    t.save({"Makefile": makefile,
            "hello.h": hello_h,
            "hello.cpp": hello_cpp,
            "app.cpp": main_cpp,
            "conanfile.py": conanfile_py,
            "profile": profile})

    t.run("install . --profile:host=profile --profile:build=default")
    t.run("build .")

    libhello = os.path.join(t.current_folder, "libhello.a")
    app = os.path.join(t.current_folder, "app")
    assert os.path.isfile(libhello)
    assert os.path.isfile(app)

    expected_arch = to_apple_arch(arch)

    t.run_command('lipo -info "%s"' % libhello)
    assert "architecture: %s" % expected_arch in t.out

    t.run_command('lipo -info "%s"' % app)
    assert "architecture: %s" % expected_arch in t.out

    if arch == "x86_64":
        t.run_command('"%s"' % app)
        assert "running catalyst 130100" in t.out
