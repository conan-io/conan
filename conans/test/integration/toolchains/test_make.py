import platform
import textwrap
import unittest

import pytest
from nose.plugins.attrib import attr

from conans.client.tools import which
from conans.test.assets.sources import gen_function_h, gen_function_cpp
from conans.test.utils.tools import TestClient


@attr("slow")
@attr("toolchain")
@pytest.mark.slow
@pytest.mark.toolchain
@pytest.mark.tool_autotools
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
            from conans import ConanFile
            from conan.tools.gnu import MakeToolchain
            class App(ConanFile):
                settings = "os", "arch", "compiler", "build_type"
                def generate(self):
                    tc = MakeToolchain(self)
                    tc.variables["TEST_VAR"] = "TestVarValue"
                    tc.preprocessor_definitions["TEST_DEFINITION"] = "TestPpdValue"
                    tc.generate()

                def build(self):
                    self.run("make -C ..")

            """)
        hello_h = gen_function_h(name="hello")
        hello_cpp = gen_function_cpp(name="hello", preprocessor=["TEST_DEFINITION"])

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
            from conans import ConanFile
            from conan.tools.gnu import MakeToolchain
            class App(ConanFile):
                settings = "os", "arch", "compiler", "build_type"
                def generate(self):
                    tc = MakeToolchain(self)
                    tc.variables["TEST_VAR"] = "TestVarValue"
                    tc.preprocessor_definitions["TEST_DEFINITION"] = "TestPpdValue"
                    tc.generate()

                def build(self):
                    self.run("make -C ..")

            """)

        hello_h = gen_function_h(name="hello")
        hello_cpp = gen_function_cpp(name="hello", preprocessor=["TEST_DEFINITION"])

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
