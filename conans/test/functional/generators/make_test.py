import os
import platform
import unittest

import pytest

from conans.client.tools import replace_in_file
from conans.test.utils.tools import TestClient


class MakeGeneratorTest(unittest.TestCase):

    @pytest.mark.slow
    @pytest.mark.tool_autotools
    @pytest.mark.skipif(platform.system() != "Linux", reason="Requires make")
    def test_complete_creation_reuse(self):
        client = TestClient(path_with_spaces=False)
        client.run("new myhello/1.0.0 --sources")
        client.run("create . danimtb/testing")
        hellowrapper_include = """
#pragma once

void hellowrapper();
"""
        hellowrapper_impl = """
#include "myhello.h"

#include "hellowrapper.h"

void hellowrapper(){
    myhello();
}
"""
        makefile = """
include conanbuildinfo.mak

#----------------------------------------
#     Make variables for a sample App
#----------------------------------------

INCLUDE_DIRS = \
./include

CXX_SRCS = \
src/hellowrapper.cpp

CXX_OBJ_FILES = \
hellowrapper.o

STATIC_LIB_FILENAME = \
libhellowrapper.a

SHARED_LIB_FILENAME = \
libhellowrapper.so

CXXFLAGS += \
-fPIC

#----------------------------------------
#     Prepare flags from variables
#----------------------------------------

CFLAGS              += $(CONAN_CFLAGS)
CXXFLAGS            += $(CONAN_CXXFLAGS)
CPPFLAGS            += $(addprefix -I, $(INCLUDE_DIRS) $(CONAN_INCLUDE_DIRS))
CPPFLAGS            += $(addprefix -D, $(CONAN_DEFINES))
LDFLAGS             += $(addprefix -L, $(CONAN_LIB_DIRS))
LDLIBS              += $(addprefix -l, $(CONAN_LIBS))
SHAREDLINKFLAGS     += $(CONAN_SHAREDLINKFLAGS)

#----------------------------------------
#     Make Commands
#----------------------------------------

COMPILE_CXX_COMMAND         ?= \
	g++ -c $(CPPFLAGS) $(CXXFLAGS) $< -o $@

CREATE_SHARED_LIB_COMMAND   ?= \
	g++ -shared $(CXX_OBJ_FILES) \
	$(CXXFLAGS) $(LDFLAGS) $(LDLIBS) $(SHAREDLINKFLAGS) \
	-o $(SHARED_LIB_FILENAME)

CREATE_STATIC_LIB_COMMAND   ?= \
	ar rcs $(STATIC_LIB_FILENAME) $(CXX_OBJ_FILES)


#----------------------------------------
#     Make Rules
#----------------------------------------

.PHONY                  :   static shared
static                  :   $(STATIC_LIB_FILENAME)
shared                  :   $(SHARED_LIB_FILENAME)

$(SHARED_LIB_FILENAME)  :   $(CXX_OBJ_FILES)
	$(CREATE_SHARED_LIB_COMMAND)

$(STATIC_LIB_FILENAME)  :   $(CXX_OBJ_FILES)
	$(CREATE_STATIC_LIB_COMMAND)

$(CXX_OBJ_FILES)        :   $(CXX_SRCS)
	$(COMPILE_CXX_COMMAND)
"""
        conanfile = """
from conans import ConanFile

class HelloWrapper(ConanFile):
    name = "hellowrapper"
    version = "1.0"
    settings = "os", "compiler", "build_type", "arch"
    requires = "myhello/1.0.0@danimtb/testing"
    generators = "make"
    exports_sources = "include/hellowrapper.h", "src/hellowrapper.cpp", "Makefile"
    options = {"shared": [True, False]}
    default_options = {"shared": False}

    def build(self):
        make_command = "make shared" if self.options.shared else "make static"
        self.run(make_command)

    def package(self):
        self.copy("*.h", dst="include", src="include")
        self.copy("*.so", dst="lib", keep_path=False)
        self.copy("*.a", dst="lib", keep_path=False)

    def package_info(self):
        self.cpp_info.libs = ["hellowrapper"]
"""
        client.save({"include/hellowrapper.h": hellowrapper_include,
                     "src/hellowrapper.cpp": hellowrapper_impl,
                     "Makefile": makefile,
                     "conanfile.py": conanfile}, clean_first=True)
        client.run("create . danimtb/testing")
        # Test also shared
        client.run("create . danimtb/testing -o hellowrapper:shared=True")

        main = """
#include "hellowrapper.h"
int main()
{
     hellowrapper();
     return 0;
}
"""
        makefile = """
include conanbuildinfo.mak

#----------------------------------------
#     Make variables for a sample App
#----------------------------------------

CXX_SRCS = \
src/main.cpp

CXX_OBJ_FILES = \
main.o

EXE_FILENAME = \
main

CXXFLAGS += \
-fPIC

EXELINKFLAGS += \
-fPIE

#----------------------------------------
#     Prepare flags from variables
#----------------------------------------

CFLAGS              += $(CONAN_CFLAGS)
CXXFLAGS            += $(CONAN_CXXFLAGS)
CPPFLAGS            += $(addprefix -I, $(CONAN_INCLUDE_DIRS))
CPPFLAGS            += $(addprefix -D, $(CONAN_DEFINES))
LDFLAGS             += $(addprefix -L, $(CONAN_LIB_DIRS))
LDLIBS              += $(addprefix -l, $(CONAN_LIBS))
EXELINKFLAGS        += $(CONAN_EXELINKFLAGS)

#----------------------------------------
#     Make Commands
#----------------------------------------

COMPILE_CXX_COMMAND         ?= \
	g++ -c $(CPPFLAGS) $(CXXFLAGS) $< -o $@

CREATE_EXE_COMMAND          ?= \
	g++ $(CXX_OBJ_FILES) \
	$(CXXFLAGS) $(LDFLAGS) $(LDLIBS) $(EXELINKFLAGS) \
	-o $(EXE_FILENAME)


#----------------------------------------
#     Make Rules
#----------------------------------------

.PHONY                  :   exe
exe                     :   $(EXE_FILENAME)

$(EXE_FILENAME)         :   $(CXX_OBJ_FILES)
	$(CREATE_EXE_COMMAND)

$(CXX_OBJ_FILES)        :   $(CXX_SRCS)
	$(COMPILE_CXX_COMMAND)
"""
        conanfile_txt = """
[requires]
hellowrapper/1.0@danimtb/testing

[generators]
make
"""
        client.save({"src/main.cpp": main,
                     "Makefile": makefile,
                     "conanfile.txt": conanfile_txt},
                    clean_first=True)

        client.run("install .")
        client.run_command("make exe")
        client.run_command("./main")
        self.assertIn("Hello World Release!", client.out)

        # Test it also builds with shared lib
        client.run("install . -o hellowrapper:shared=True")
        client.run_command("rm main main.o")
        client.run_command("make exe")
        client.run_command("ldd main")
        self.assertIn("libhellowrapper.so", client.out)
