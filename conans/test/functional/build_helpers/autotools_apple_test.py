import os
import platform
import textwrap
import unittest

from parameterized import parameterized

from conans.client.tools.apple import to_apple_arch
from conans.test.assets.sources import gen_function_cpp, gen_function_h
from conans.test.utils.tools import TestClient


@unittest.skipUnless(platform.system() == "Darwin", "requires Xcode")
class AutoToolsAppleTest(unittest.TestCase):
    @parameterized.expand([("x86_64", "Macos", "10.14"),
                           ("armv8", "iOS", "10.0"),
                           ("armv7", "iOS", "10.0"),
                           ("x86", "iOS", "10.0"),
                           ("x86_64", "iOS", "10.0")
                           ])
    def test_makefile_arch(self, arch, os_, os_version):
        self.arch = arch
        self.os = os_
        self.os_version = os_version

        makefile = textwrap.dedent("""
            .PHONY: all
            all: libhello.a app

            app: main.o libhello.a
            	$(CXX) $(CFLAGS) -o app main.o -lhello -L.

            libhello.a: hello.o
            	$(AR) rcs libhello.a hello.o

            main.o: main.cpp
            	$(CXX) $(CFLAGS) -c -o main.o main.cpp

            hello.o: hello.cpp
            	$(CXX) $(CFLAGS) -c -o hello.o hello.cpp
            """)

        profile = textwrap.dedent("""
            include(default)
            [settings]
            os = {os}
            os.version = {os_version}
            arch = {arch}
            """).format(os=self.os, arch=self.arch, os_version=self.os_version)

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

        self.t = TestClient()
        hello_h = gen_function_h(name="hello")
        hello_cpp = gen_function_cpp(name="hello")
        main_cpp = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])

        self.t.save({"Makefile": makefile,
                     "hello.h": hello_h,
                     "hello.cpp": hello_cpp,
                     "main.cpp": main_cpp,
                     "conanfile.py": conanfile_py,
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
