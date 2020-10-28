import platform
import textwrap
import unittest

from nose.plugins.attrib import attr

from conans.test.utils.tools import TestClient
from conans.client.tools import which


@attr("slow")
@attr("toolchain")
class MakeToolchainTest(unittest.TestCase):

    @unittest.skipUnless(platform.system() in ["Linux"], "Requires linux")
    def test_toolchain_posix(self):
        client = TestClient(path_with_spaces=False)
        settings = {
            "arch": "x86_64",
            "build_type": "Release",
            "compiler": "gcc",
            "compiler.version": "9",
            "compiler.libcxx": "libstdc++11",
        }

        settings_str = " ".join('-s %s="%s"' % (k, v) for k, v in settings.items() if v)

        conanfile = textwrap.dedent("""
            from conans import ConanFile, MakeToolchain
            class App(ConanFile):
                settings = "os", "arch", "compiler", "build_type"
                def toolchain(self):
                    tc = MakeToolchain(self)
                    tc.variables["TEST_VAR"] = "TestVarValue"
                    tc.preprocessor_definitions["TEST_DEFINITION"] = "TestPpdValue"
                    tc.write_toolchain_files()

                def build(self):
                    self.run("make -C ..")

            """)

        hello_h = textwrap.dedent("""
            #pragma once
            #define HELLO_MSG "Release"
            #ifdef WIN32
              #define APP_LIB_EXPORT __declspec(dllexport)
            #else
              #define APP_LIB_EXPORT
            #endif
            APP_LIB_EXPORT void hello();
            """)

        hello_cpp = textwrap.dedent("""
            #include <iostream>
            #include "hello.h"

            void hello() {
                std::cout << "Hello World " << HELLO_MSG << "!" << std::endl;
                std::cout << "App: Release!" << std::endl;
                std::cout << "TEST_DEFINITION: " << TEST_DEFINITION << "\\n";
            }
            """)

        makefile = textwrap.dedent("""
            include conan_toolchain.mak

            #-------------------------------------------------
            #     Make variables for a sample App
            #-------------------------------------------------

            OUT_DIR             ?= out
            SRC_DIR             ?= src
            INCLUDE_DIR         ?= include

            PROJECT_NAME        = hello
            STATIC_LIB_FILENAME = lib$(PROJECT_NAME).a

            SRCS                += $(wildcard $(SRC_DIR)/*.cpp)
            OBJS                += $(patsubst $(SRC_DIR)/%.cpp,$(OUT_DIR)/%.o,$(SRCS))
            CPPFLAGS            += $(addprefix -I,$(INCLUDE_DIR))

            #-------------------------------------------------
            #     Append CONAN_ variables to standards
            #-------------------------------------------------

            CPPFLAGS += $(CONAN_TC_CPPFLAGS)

            #-------------------------------------------------
            #     Print variables to be tested
            #-------------------------------------------------

            $(info >> CPPFLAGS: $(CPPFLAGS))
            $(info >> TEST_VAR: $(TEST_VAR))

            #-------------------------------------------------
            #     Make Rules
            #-------------------------------------------------


            .PHONY               : static

            static               : $(OBJS)
            	$(AR) $(ARFLAGS) $(OUT_DIR)/$(STATIC_LIB_FILENAME) $(OBJS)

            $(OUT_DIR)/%.o       : $(SRC_DIR)/%.cpp $(OUT_DIR)
            	$(CXX) $(CXXFLAGS) $(CPPFLAGS) -c $< -o $@

            $(OUT_DIR):
            	-mkdir $@
            """)

        files_to_save = {
            "conanfile.py": conanfile,
            "Makefile": makefile,
            "src/hello.cpp": hello_cpp,
            "include/hello.h": hello_h
        }

        client.save(files_to_save, clean_first=True)
        client.run("install . hello/0.1@ %s" % settings_str)
        client.run_command("make static")
        client.run_command("nm -C out/libhello.a | grep 'hello()'")
        self.assertIn("hello()", client.out)

    @unittest.skipUnless(platform.system() in ["Windows"], "Requires mingw32-make")
    @unittest.skipIf(which("mingw32-make") is None, "Needs mingw32-make")
    def test_toolchain_windows(self):
        client = TestClient(path_with_spaces=False)

        settings = {
            "arch": "x86_64",
            "build_type": "Release",
            "compiler": "gcc",
            "compiler.version": "9",
            "compiler.libcxx": "libstdc++11",
        }
        settings_str = " ".join('-s %s="%s"' % (k, v) for k, v in settings.items() if v)

        conanfile = textwrap.dedent("""
            from conans import ConanFile, MakeToolchain
            class App(ConanFile):
                settings = "os", "arch", "compiler", "build_type"
                def toolchain(self):
                    tc = MakeToolchain(self)
                    tc.variables["TEST_VAR"] = "TestVarValue"
                    tc.preprocessor_definitions["TEST_DEFINITION"] = "TestPpdValue"
                    tc.write_toolchain_files()

                def build(self):
                    self.run("make -C ..")

            """)

        hello_h = textwrap.dedent("""
            #pragma once
            #define HELLO_MSG "{0}"
            #ifdef WIN32
              #define APP_LIB_EXPORT __declspec(dllexport)
            #else
              #define APP_LIB_EXPORT
            #endif
            APP_LIB_EXPORT void hello();
            """)

        hello_cpp = textwrap.dedent("""
            #include <iostream>
            #include "hello.h"

            void hello() {
                std::cout << "Hello World " << HELLO_MSG << "!" << std::endl;
                std::cout << "App: Release!" << std::endl;
                std::cout << "TEST_DEFINITION: " << TEST_DEFINITION << "\\n";
            }
            """)

        makefile = textwrap.dedent("""
            include conan_toolchain.mak

            #-------------------------------------------------
            #     Make variables for a sample App
            #-------------------------------------------------

            OUT_DIR             ?= out
            SRC_DIR             ?= src
            INCLUDE_DIR         ?= include

            PROJECT_NAME        = hello
            STATIC_LIB_FILENAME = lib$(PROJECT_NAME).a

            SRCS                += $(wildcard $(SRC_DIR)/*.cpp)
            OBJS                += $(patsubst $(SRC_DIR)/%.cpp,$(OUT_DIR)/%.o,$(SRCS))
            CPPFLAGS            += $(addprefix -I,$(INCLUDE_DIR))

            #-------------------------------------------------
            #     Append CONAN_ variables to standards
            #-------------------------------------------------

            CPPFLAGS += $(CONAN_TC_CPPFLAGS)

            #-------------------------------------------------
            #     Print variables to be tested
            #-------------------------------------------------

            $(info >> CPPFLAGS: $(CPPFLAGS))
            $(info >> TEST_VAR: $(TEST_VAR))

            #-------------------------------------------------
            #     Make Rules
            #-------------------------------------------------


            .PHONY               : static

            static               : $(OBJS)
            	$(AR) $(ARFLAGS) $(OUT_DIR)/$(STATIC_LIB_FILENAME) $(OBJS)

            $(OUT_DIR)/%.o       : $(SRC_DIR)/%.cpp $(OUT_DIR)
            	$(CXX) $(CXXFLAGS) $(CPPFLAGS) -c $< -o $@

            $(OUT_DIR):
            	-mkdir $@
            """)

        files_to_save = {
            "conanfile.py": conanfile,
            "Makefile": makefile,
            "src/hello.cpp": hello_cpp,
            "include/hello.h": hello_h
        }

        client.save(files_to_save, clean_first=True)
        client.run("install . hello/0.1@ %s" % settings_str)
        client.run_command("mingw32-make static")
        client.run_command("nm -C out/libhello.a | find \"hello()\"")
        self.assertIn("hello()", client.out)
