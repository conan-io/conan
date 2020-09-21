import os
import platform
import textwrap
import unittest

from nose.plugins.attrib import attr

from conans.test.utils.tools import TestClient

from parameterized.parameterized import parameterized


@attr("slow")
@attr("toolchain")
@unittest.skipUnless(platform.system() == "Linux", "Only for Linux")
class LinuxTest(unittest.TestCase):
    @parameterized.expand([("exe", "Release"),
                           ("exe", "Debug"),
                           ("exe", "Release"),
                           ("shared", "Release"),
                           ("static", "Release"),
                           ])
    def test_toolchain_linux(self, target, build_type):
        client = TestClient(path_with_spaces=False)

        settings = {
            "build_type": build_type
        }
        options = {
            "fPIC": "True",
        }

        if target == "exe":
            conanfile_options = 'options = {"fPIC": [True, False]}'
            conanfile_default_options = 'default_options = {"fPIC": True}'
        else:
            conanfile_options = 'options = {"shared": [True, False], "fPIC": [True, False]}'
            conanfile_default_options = 'default_options = {"shared": False, "fPIC": True}'
            if target == "shared":
                options["shared"] = True

        settings_str = " ".join('-s %s="%s"' % (k, v) for k, v in settings.items() if v)
        options_str = " ".join("-o %s=%s" % (k, v) for k, v in options.items()) if options else ""

        conanfile = textwrap.dedent("""
            from conans import ConanFile, MakeToolchain
            class App(ConanFile):
                settings = "os", "arch", "compiler", "build_type"
                {options}
                {default_options}
                def toolchain(self):
                    tc = MakeToolchain(self)
                    tc.definitions["SOME_DEFINITION"] = "SomeValue"
                    tc.write_toolchain_files()

                def build(self):
                    self.run("make -C ..")

            """).format(options=conanfile_options, default_options=conanfile_default_options)

        hello_h = textwrap.dedent("""
            #pragma once
            #define HELLO_MSG "{0}"
            #ifdef WIN32
              #define APP_LIB_EXPORT __declspec(dllexport)
            #else
              #define APP_LIB_EXPORT
            #endif
            APP_LIB_EXPORT void hello();
            """.format(build_type))

        hello_cpp = textwrap.dedent("""
            #include <iostream>
            #include "hello.h"

            void hello() {
                std::cout << "Hello World " << HELLO_MSG << "!" << std::endl;
                #ifdef NDEBUG
                std::cout << "App: Release!" << std::endl;
                #else
                std::cout << "App: Debug!" << std::endl;
                #endif
                std::cout << "SOME_DEFINITION: " << SOME_DEFINITION << "\\n";
            }
            """)

        # only used for the executable test case
        main = textwrap.dedent("""
            #include "hello.h"
            int main() {
                hello();
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
            EXE_FILENAME        = $(PROJECT_NAME).bin
            STATIC_LIB_FILENAME = lib$(PROJECT_NAME).a
            SHARED_LIB_FILENAME = lib$(PROJECT_NAME).so

            SRCS                += $(wildcard $(SRC_DIR)/*.cpp)
            OBJS                += $(patsubst $(SRC_DIR)/%.cpp,$(OUT_DIR)/%.o,$(SRCS))
            CPPFLAGS            += $(addprefix -I,$(INCLUDE_DIR))

            #-------------------------------------------------
            #     Append CONAN_ variables to standards
            #-------------------------------------------------

            $(call CONAN_TC_SETUP)

            # The above function should append CONAN_TC flags to standard flags
            $(info >> CFLAGS: $(CFLAGS))
            $(info >> CXXFLAGS: $(CXXFLAGS))
            $(info >> CPPFLAGS: $(CPPFLAGS))
            $(info >> LDFLAGS: $(LDFLAGS))
            $(info >> LDLIBS: $(LDLIBS))

            #-------------------------------------------------
            #     Make Rules
            #-------------------------------------------------


            .PHONY               : exe static shared

            exe                  : $(OBJS)
            	$(CXX) $(OBJS) $(LDFLAGS) $(LDLIBS) -o $(OUT_DIR)/$(EXE_FILENAME)

            static               : $(OBJS)
            	$(AR) $(ARFLAGS) $(OUT_DIR)/$(STATIC_LIB_FILENAME) $(OBJS)

            shared               : $(OBJS)
            	$(CXX) -shared $(OBJS) $(LDFLAGS) $(LDLIBS) -o $(OUT_DIR)/$(SHARED_LIB_FILENAME)

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
        if target == "exe":
            files_to_save["src/main.cpp"] = main

        client.save(files_to_save, clean_first=True)
        client.run("install . hello/0.1@ %s %s" % (settings_str, options_str))

        if target == "exe":
            client.run_command("make exe")
            client.run_command("./out/hello.bin")
            self.assertIn("Hello World {}!".format(build_type), client.out)
        elif target == "shared":
            client.run_command("make shared")
            client.run_command("nm -C out/libhello.so | grep 'hello()'")
            self.assertIn("hello()", client.out)
        elif target == "static":
            client.run_command("make static")
            client.run_command("nm -C out/libhello.a | grep 'hello()'")
            self.assertIn("hello()", client.out)
