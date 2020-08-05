import os
import platform
import textwrap
import unittest

from nose.plugins.attrib import attr

from conans.test.utils.tools import TestClient

from parameterized.parameterized import parameterized


@attr("toolchain")
class Base(unittest.TestCase):
    conanfile = textwrap.dedent("""
        from conans import ConanFile, MakeToolchain
        class App(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            requires = "hello/0.1"
            generators = "make"
            options = {"shared": [True, False], "fPIC": [True, False]}
            default_options = {"shared": False, "fPIC": True}
            def toolchain(self):
                tc = MakeToolchain(self)
                tc.definitions["SOME_DEFINITION"] = "SomeValue"
                tc.write_toolchain_files()

            def build(self):
                self.run("make -C ..")

        """)

    app_h = textwrap.dedent("""
        #pragma once
        #ifdef WIN32
          #define APP_LIB_EXPORT __declspec(dllexport)
        #else
          #define APP_LIB_EXPORT
        #endif
        APP_LIB_EXPORT void app();
        """)

    app_lib_cpp = textwrap.dedent("""
        #include <iostream>
        #include "app.h"
        #include "hello.h"
        void app() {
            std::cout << "Hello: " << HELLO_MSG <<std::endl;
            #ifdef NDEBUG
            std::cout << "App: Release!" <<std::endl;
            #else
            std::cout << "App: Debug!" <<std::endl;
            #endif
            std::cout << "SOME_DEFINITION: " << SOME_DEFINITION << "\\n";
        }
        """)

    app = textwrap.dedent("""
        #include "app.h"
        int main() {
            app();
        }
        """)

    makefile = textwrap.dedent("""
        include build/conan_toolchain.mak
        include build/conanbuildinfo.mak
        ifndef CONAN_TOOLCHAIN_INCLUDED
            $(error >> Not using toolchain)
        endif

        # These lines workaround deficiency in makefile generator
        # plan to add function to that generator CONAN_BASIC_SETUP
        # just like CONAN_TC_SETUP. Can remove two lines below after that.
        CPPFLAGS += $(addprefix -D,$(CONAN_DEFINES))
        CPPFLAGS += $(addprefix -I,$(CONAN_INCLUDE_DIRS))

        $(info >> CONAN_TC_LIBCXX: $(CONAN_TC_LIBCXX))
        $(info >> CONAN_TC_CFLAGS: $(CONAN_TC_CFLAGS))
        $(info >> CONAN_TC_CXXFLAGS: $(CONAN_TC_CXXFLAGS))
        $(info >> CONAN_TC_CPPFLAGS: $(CONAN_TC_CPPFLAGS))
        $(info >> CONAN_TC_LDFLAGS: $(CONAN_TC_LDFLAGS))
        $(info >> CONAN_TC_SET_FPIC: $(CONAN_TC_SET_FPIC))
        $(info >> CONAN_TC_SET_SHARED: $(CONAN_TC_SET_SHARED))

        $(call CONAN_TC_SETUP)

        # The above function should append CONAN_TC flags to standard flags
        $(info >> CFLAGS: $(CFLAGS))
        $(info >> CXXFLAGS: $(CXXFLAGS))
        $(info >> CPPFLAGS: $(CPPFLAGS))
        $(info >> LDFLAGS: $(LDFLAGS))
        $(info >> LDLIBS: $(LDLIBS))

        .PHONY               : all

        all:;
        """)

    def setUp(self):
        self.client = TestClient(path_with_spaces=False)
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conans.tools import save
            import os
            class Pkg(ConanFile):
                settings = "build_type"
                def package(self):
                    save(os.path.join(self.package_folder, "include/hello.h"),
                         '#define HELLO_MSG "%s"' % self.settings.build_type)
            """)
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . hello/0.1@ -s build_type=Debug")
        self.client.run("create . hello/0.1@ -s build_type=Release")
        # Prepare the actual consumer package
        self.client.save({"conanfile.py": self.conanfile,
                          "Makefile": self.makefile,
                          "app.cpp": self.app,
                          "app_lib.cpp": self.app_lib_cpp,
                          "app.h": self.app_h})

    def _run_build(self, settings=None, options=None):
        # Build the profile according to the settings provided
        settings = settings or {}
        settings = " ".join('-s %s="%s"' % (k, v) for k, v in settings.items() if v)
        options = " ".join("-o %s=%s" % (k, v) for k, v in options.items()) if options else ""

        # Run the configure corresponding to this test case
        build_directory = os.path.join(self.client.current_folder, "build").replace("\\", "/")

        with self.client.chdir(build_directory):
            self.client.run("install .. %s %s" % (settings, options))
            install_out = self.client.out
            self.client.run("build ..")
        return install_out


@unittest.skipUnless(platform.system() == "Linux", "Only for Linux")
class LinuxTest(Base):
    @parameterized.expand([("Debug", "14", "x86", "libstdc++", False, False),
                           ("Release", "gnu14", "x86_64", "libstdc++11", True, False),
                           ("Release", "gnu14", "x86_64", "libstdc++11", False, True)])
    def test_toolchain_linux(self, build_type, cppstd, arch, libcxx, shared, fpic):

        settings = {"compiler": "gcc",
                    "compiler.version": "8",
                    "compiler.cppstd": cppstd,
                    "compiler.libcxx": libcxx,
                    "arch": arch,
                    "build_type": build_type}
        options = {"shared": shared, "fPIC": fpic}
        self._run_build(settings, options)

        expected = {
            "CFLAGS": [],
            "CXXFLAGS": [],
            "CPPFLAGS": [],
            "LDFLAGS": [],
        }

        expected["CPPFLAGS"].append('-DSOME_DEFINITION=\\"SomeValue\\"')
        if libcxx == "libstdc++11":
            expected["CPPFLAGS"].append('-DGLIBCXX_USE_CXX11_ABI=1')
        else:
            expected["CPPFLAGS"].append('-DGLIBCXX_USE_CXX11_ABI=0')
        if build_type == "Release":
            expected["CPPFLAGS"].append('-DNDEBUG')
            if fpic:
                expected["CFLAGS"].append('-fPIC')
                expected["CXXFLAGS"].append('-fPIC')
                if shared:
                    expected["LDFLAGS"].append('-fPIC')
                else:
                    expected["LDFLAGS"].append('-pie')

        if shared:
            expected["LDFLAGS"].append('-shared')

        def _verify_out(marker=">> "):
            output_flag_lines = str(self.client.out).splitlines()
            actual_flags = {}
            for line in filter(lambda ln: marker in ln, output_flag_lines):
                # print(line)
                var_name, flags = line.split(marker)[1].split(":", 1)
                actual_flags[var_name.strip()] = flags.split()

            # Verify that every item in the list of expected flags for each variable is in the output
            for var_name, expected_flags in expected.items():
                all(self.assertIn(flag, actual_flags[var_name]) for flag in expected_flags)

        _verify_out()
