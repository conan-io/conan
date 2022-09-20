import os
import platform
import textwrap
import unittest

import pytest
from parameterized import parameterized

from conans.client.tools.apple import to_apple_arch
from conans.test.assets.autotools import gen_makefile
from conans.test.assets.sources import gen_function_cpp, gen_function_h
from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Darwin", reason="requires Xcode")
class AutoToolsAppleTest(unittest.TestCase):
    makefile = gen_makefile(apps=["app"], libs=["hello"])

    conanfile_py = textwrap.dedent("""
        from conans import ConanFile, tools, AutoToolsBuildEnvironment

        class App(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            options = {"shared": [True, False], "fPIC": [True, False]}
            default_options = {"shared": False, "fPIC": True}

            def config_options(self):
                if self.settings.os == "Windows":
                    del self.options.fPIC

            def build(self):
                env_build = AutoToolsBuildEnvironment(self)
                env_build.make()
        """)

    @parameterized.expand([("x86_64", "Macos", "10.14"),
                           ("armv8", "iOS", "10.0"),
                           ("armv7", "iOS", "10.0"),
                           ("x86", "iOS", "10.0"),
                           ("x86_64", "iOS", "10.0"),
                           ("armv8", "Macos", "10.14")  # M1
                           ])
    def test_makefile_arch(self, arch, os_, os_version):
        self.arch = arch
        self.os = os_
        self.os_version = os_version

        profile = textwrap.dedent("""
            include(default)
            [settings]
            os = {os}
            os.version = {os_version}
            arch = {arch}
            """).format(os=self.os, arch=self.arch, os_version=self.os_version)

        self.t = TestClient()
        hello_h = gen_function_h(name="hello")
        hello_cpp = gen_function_cpp(name="hello")
        main_cpp = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])

        self.t.save({"Makefile": self.makefile,
                     "hello.h": hello_h,
                     "hello.cpp": hello_cpp,
                     "app.cpp": main_cpp,
                     "conanfile.py": self.conanfile_py,
                     "profile": profile})

        self.t.run("install . --profile:host=profile")
        self.t.run("build .")

        libhello = os.path.join(self.t.current_folder, "libhello.a")
        app = os.path.join(self.t.current_folder, "app")
        self.assertTrue(os.path.isfile(libhello))
        self.assertTrue(os.path.isfile(app))

        expected_arch = to_apple_arch(self.arch)

        self.t.run_command('lipo -info "%s"' % libhello)
        self.assertIn("architecture: %s" % expected_arch, self.t.out)

        self.t.run_command('lipo -info "%s"' % app)
        self.assertIn("architecture: %s" % expected_arch, self.t.out)

    @parameterized.expand([("x86_64",), ("armv8",)])
    def test_catalyst(self, arch):
        profile = textwrap.dedent("""
            include(default)
            [settings]
            os = Macos
            os.version = 12.0
            os.sdk = macosx
            os.subsystem = catalyst
            os.subsystem.ios_version = 13.1
            arch = {arch}
            """).format(arch=arch)

        self.t = TestClient()
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

        self.t.save({"Makefile": self.makefile,
                     "hello.h": hello_h,
                     "hello.cpp": hello_cpp,
                     "app.cpp": main_cpp,
                     "conanfile.py": self.conanfile_py,
                     "profile": profile})

        self.t.run("install . --profile:host=profile")
        self.t.run("build .")

        libhello = os.path.join(self.t.current_folder, "libhello.a")
        app = os.path.join(self.t.current_folder, "app")
        self.assertTrue(os.path.isfile(libhello))
        self.assertTrue(os.path.isfile(app))

        expected_arch = to_apple_arch(arch)

        self.t.run_command('lipo -info "%s"' % libhello)
        self.assertIn("architecture: %s" % expected_arch, self.t.out)

        self.t.run_command('lipo -info "%s"' % app)
        self.assertIn("architecture: %s" % expected_arch, self.t.out)

        if arch == "x86_64":
            self.t.run_command('"%s"' % app)
            self.assertIn("running catalyst 130100", self.t.out)
