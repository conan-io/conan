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
                self.run("make -C .. app")

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

        $(info >> CONAN_BUILD_TYPE: $(CONAN_BUILD_TYPE))
        $(info >> CONAN_TC_CFLAGS: $(CONAN_TC_CFLAGS))
        $(info >> CONAN_TC_CXXFLAGS: $(CONAN_TC_CXXFLAGS))
        $(info >> CONAN_TC_DEFINES: $(CONAN_TC_DEFINES))
        $(info >> CONAN_TC_LDFLAGS: $(CONAN_TC_LDFLAGS))


        CFLAGS += $(CONAN_TC_CFLAGS)
        CXXFLAGS += $(CONAN_TC_CXXFLAGS)
        LDFLAGS += $(CONAN_TC_LDFLAGS)
        CPPFLAGS += $(addprefix -D,$(CONAN_TC_DEFINES))
        CPPFLAGS += $(addprefix -I,$(CONAN_INCLUDE_DIRS))

        .PHONY               : app

        app                  : app.obj app_lib.obj
        	$(CXX) $(LDFLAGS) app.obj app_lib.obj -o $@

        %.obj              : %.cpp
        	$(CXX) $(CXXFLAGS) $(CPPFLAGS) -c $< -o $@
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

    def _modify_code(self):
        content = self.client.load("app_lib.cpp")
        content = content.replace("App:", "AppImproved:")
        self.client.save({"app_lib.cpp": content})

        content = self.client.load("CMakeLists.txt")
        content = content.replace(">>", "++>>")
        self.client.save({"CMakeLists.txt": content})

    def _incremental_build(self, build_type=None):
        build_directory = os.path.join(self.client.current_folder, "build").replace("\\", "/")
        with self.client.chdir(build_directory):
            config = "--config %s" % build_type if build_type else ""
            self.client.run_command("cmake --build . %s" % config)

    def _run_app(self, build_type, bin_folder=False, msg="App", dyld_path=None):
        if dyld_path:
            build_directory = os.path.join(self.client.current_folder, "build").replace("\\", "/")
            command_str = 'DYLD_LIBRARY_PATH="%s" ../app' % build_directory
        else:
            command_str = "../app.exe" % build_type if bin_folder else "./app"

        self.client.run_command(command_str)
        self.assertIn("Hello: %s" % build_type, self.client.out)
        self.assertIn("%s: %s!" % (msg, build_type), self.client.out)
        self.assertIn("SOME_DEFINITION: SomeValue", self.client.out)


@unittest.skipUnless(platform.system() == "Linux", "Only for Linux")
class LinuxTest(Base):
    @parameterized.expand([("Debug",  "14", "x86", "libstdc++", True),
                           ("Release", "gnu14", "x86_64", "libstdc++11", False)])
    def test_toolchain_linux(self, build_type, cppstd, arch, libcxx, shared):
        settings = {"compiler": "gcc",
                    "compiler.cppstd": cppstd,
                    "compiler.libcxx": libcxx,
                    "arch": arch,
                    "build_type": build_type}
        self._run_build(settings, {"shared": shared})

        defines_expected = 'SOME_DEFINITION=\\"SomeValue\\"'
        if libcxx == "libstdc++11":
            defines_expected += " GLIBCXX_USE_CXX11_ABI=1"
        else:
            defines_expected += " GLIBCXX_USE_CXX11_ABI=0"
        if build_type == "Release":
            defines_expected += " NDEBUG"

        vals = {"CONAN_TC_CFLAGS": "-fPIC" if build_type == "Release" else "",
                "CONAN_TC_CXXFLAGS": "-fPIC" if build_type == "Release" else "",
                "CONAN_TC_DEFINES": defines_expected,
                "CONAN_TC_LDFLAGS": "",
                }

        def _verify_out(marker=">>"):
            out = str(self.client.out).splitlines()
            for k, v in vals.items():
                self.assertIn("%s %s: %s" % (marker, k, v), out)

        _verify_out()

        self._run_app(build_type)

        # self._modify_code()
        # self._incremental_build()
        # _verify_out(marker="++>>")
        # self._run_app(build_type, msg="AppImproved")


# @unittest.skipUnless(platform.system() == "Darwin", "Only for Apple")
# class AppleTest(Base):
#     @parameterized.expand([("Debug",  "14",  True),
#                            ("Release", "", False)])
#     def test_toolchain_apple(self, build_type, cppstd, shared):
#         settings = {"compiler": "apple-clang",
#                     "compiler.cppstd": cppstd,
#                     "build_type": build_type}
#         self._run_build(settings, {"shared": shared})
#
#         self.assertIn('CMake command: cmake -G "Unix Makefiles" '
#                       '-DCMAKE_TOOLCHAIN_FILE="conan_toolchain.cmake"', self.client.out)
#
#         extensions_str = "OFF" if cppstd else ""
#         vals = {"CMAKE_CXX_STANDARD": cppstd,
#                 "CMAKE_CXX_EXTENSIONS": extensions_str,
#                 "CMAKE_BUILD_TYPE": build_type,
#                 "CMAKE_CXX_FLAGS": "-m64 -stdlib=libc++",
#                 "CMAKE_CXX_FLAGS_DEBUG": "-g",
#                 "CMAKE_CXX_FLAGS_RELEASE": "-O3 -DNDEBUG",
#                 "CMAKE_C_FLAGS": "-m64",
#                 "CMAKE_C_FLAGS_DEBUG": "-g",
#                 "CMAKE_C_FLAGS_RELEASE": "-O3 -DNDEBUG",
#                 "CMAKE_SHARED_LINKER_FLAGS": "-m64",
#                 "CMAKE_EXE_LINKER_FLAGS": "",
#                 "CMAKE_SKIP_RPATH": "1",
#                 "CMAKE_INSTALL_NAME_DIR": ""
#                 }
#
#         def _verify_out(marker=">>"):
#             if shared:
#                 self.assertIn("libapp_lib.dylib", self.client.out)
#             else:
#                 if marker == ">>":
#                     self.assertIn("libapp_lib.a", self.client.out)
#                 else:  # Incremental build not the same msg
#                     self.assertIn("Built target app_lib", self.client.out)
#             out = str(self.client.out).splitlines()
#             for k, v in vals.items():
#                 self.assertIn("%s %s: %s" % (marker, k, v), out)
#
#         _verify_out()
#
#         self._run_app(build_type, dyld_path=shared)
#
#         self._modify_code()
#         time.sleep(1)
#         self._incremental_build()
#         _verify_out(marker="++>>")
#         self._run_app(build_type, dyld_path=shared, msg="AppImproved")
#
#
# @attr("toolchain")
# class CMakeInstallTest(unittest.TestCase):
#
#     def test_install(self):
#         conanfile = textwrap.dedent("""
#             from conans import ConanFile, CMake, CMakeToolchain
#             class App(ConanFile):
#                 settings = "os", "arch", "compiler", "build_type"
#                 exports_sources = "CMakeLists.txt", "header.h"
#                 def toolchain(self):
#                     return CMakeToolchain(self)
#                 def build(self):
#                     cmake = CMake(self)
#                     cmake.configure()
#                 def package(self):
#                     cmake = CMake(self)
#                     cmake.install()
#             """)
#
#         cmakelist = textwrap.dedent("""
#             cmake_minimum_required(VERSION 2.8)
#             project(App C)
#             if(CONAN_TOOLCHAIN_INCLUDED AND CMAKE_VERSION VERSION_LESS "3.15")
#                 include("${CMAKE_BINARY_DIR}/conan_project_include.cmake")
#             endif()
#             if(NOT CMAKE_TOOLCHAIN_FILE)
#                 message(FATAL ">> Not using toolchain")
#             endif()
#             install(FILES header.h DESTINATION include)
#             """)
#         client = TestClient(path_with_spaces=False)
#         client.save({"conanfile.py": conanfile,
#                      "CMakeLists.txt": cmakelist,
#                      "header.h": "# my header file"})
#
#         # FIXME: This is broken, because the toolchain at install time, doesn't have the package
#         # folder yet. We need to define the layout for local development
#         """
#         with client.chdir("build"):
#             client.run("install ..")
#             client.run("build ..")
#             client.run("package .. -pf=mypkg")  # -pf=mypkg ignored
#         self.assertTrue(os.path.exists(os.path.join(client.current_folder, "build",
#                                                     "include", "header.h")))"""
#
#         # The create flow must work
#         client.run("create . pkg/0.1@")
#         self.assertIn("pkg/0.1 package(): Packaged 1 '.h' file: header.h", client.out)
#         ref = ConanFileReference.loads("pkg/0.1")
#         layout = client.cache.package_layout(ref)
#         package_id = layout.conan_packages()[0]
#         package_folder = layout.package(PackageReference(ref, package_id))
#         self.assertTrue(os.path.exists(os.path.join(package_folder, "include", "header.h")))
