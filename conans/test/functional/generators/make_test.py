import os
import platform
import unittest
import textwrap

from nose.plugins.attrib import attr

from conans.test.utils.tools import TestClient
from conans.client.tools import replace_in_file

from parameterized.parameterized import parameterized


class MakeGeneratorTest(unittest.TestCase):

    @unittest.skipUnless(platform.system() == "Linux", "Requires make")
    @parameterized.expand(["exe", "shared", "static"])
    @attr('slow')
    def complete_creation_reuse_test(self, target):

        # Create myhello to serve as a dependency. It must have fPIC.
        client = TestClient(path_with_spaces=False)
        client.run("new myhello/1.0.0 --sources")
        conanfile_path = os.path.join(client.current_folder, "conanfile.py")
        replace_in_file(conanfile_path, "{\"shared\": [True, False]}",
                        "{\"shared\": [True, False], \"fPIC\": [True, False]}", output=client.out)
        replace_in_file(conanfile_path, "{\"shared\": False}", "{\"shared\": False, \"fPIC\": True}",
                        output=client.out)
        client.run("create . danimtb/testing")

        # Prepare the actual consumer package
        hellowrapper_include = textwrap.dedent("""
            #pragma once

            void hellowrapper();
            """)

        hellowrapper_impl = textwrap.dedent("""
            #include "hello.h"

            #include "hellowrapper.h"

            void hellowrapper(){
                hello();
            }
            """)

        # only used for the executable test case
        main = textwrap.dedent("""
            #include "hellowrapper.h"
            int main()
            {
                 hellowrapper();
                 return 0;
            }
            """)

        makefile = textwrap.dedent("""
            include conanbuildinfo.mak

            #-------------------------------------------------
            #     Make variables for a sample App
            #-------------------------------------------------

            OUT_DIR             ?= out
            SRC_DIR             ?= src
            INCLUDE_DIR         ?= include

            PROJECT_NAME        = hellowrapper
            EXE_FILENAME        = $(PROJECT_NAME).bin
            STATIC_LIB_FILENAME = lib$(PROJECT_NAME).a
            SHARED_LIB_FILENAME = lib$(PROJECT_NAME).so

            SRCS                += $(wildcard $(SRC_DIR)/*.cpp)
            OBJS                += $(patsubst $(SRC_DIR)/%.cpp,$(OUT_DIR)/%.o,$(SRCS))
            CPPFLAGS            += $(addprefix -I,$(INCLUDE_DIR))
            CXXFLAGS            += -fPIC
            LDFLAGS             += -fPIC

            #-------------------------------------------------
            #     Append CONAN_ variables to standards
            #-------------------------------------------------

            $(call CONAN_BASIC_SETUP)

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

        if target == "exe":
            options = ''
            default_options = ''
        else:
            options = 'options = {"shared": [True, False]}'
            default_options = 'default_options = {"shared": False}'

        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class HelloWrapper(ConanFile):
                name = "hellowrapper"
                version = "1.0"
                settings = "os", "compiler", "build_type", "arch"
                requires = "myhello/1.0.0@danimtb/testing"
                generators = "make"
                exports_sources = "include/hellowrapper.h", "src/hellowrapper.cpp", "Makefile"
                {options}
                {default_options}

            """.format(options=options, default_options=default_options))

        files_to_save = {
            "include/hellowrapper.h": hellowrapper_include,
            "src/hellowrapper.cpp": hellowrapper_impl,
            "Makefile": makefile,
            "conanfile.py": conanfile
        }
        if target == "exe":
            files_to_save["src/main.cpp"] = main

        client.save(files_to_save, clean_first=True)

        if target == "exe":
            client.run("install . danimtb/testing")
            client.run_command("make exe")
            print(client.out)
            client.run_command("./out/hellowrapper.bin")
            self.assertIn("Hello World Release!", client.out)
        elif target == "shared":
            client.run("install . danimtb/testing -o hellowrapper:shared=True")
            client.run_command("make shared")
            print(client.out)
            client.run_command("nm -C out/libhellowrapper.so | grep 'hellowrapper()'")
            self.assertIn("hellowrapper()", client.out)
        elif target == "static":
            client.run("install . danimtb/testing -o hellowrapper:shared=False")
            client.run_command("make static")
            print(client.out)
            client.run_command("nm -C out/libhellowrapper.a | grep 'hellowrapper()'")
            self.assertIn("hellowrapper()", client.out)
