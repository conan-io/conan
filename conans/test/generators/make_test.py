import platform
import unittest

from conans.client.tools import chdir, replace_in_file
from conans.model.conan_file import ConanFile
from conans.model.settings import Settings
from conans.model.env_info import EnvValues
from conans.model.ref import ConanFileReference
from conans.model.build_info import CppInfo
from conans.client.generators import MakeGenerator
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient
from conans.util.files import save
import os


class MakeGeneratorTest(unittest.TestCase):

    def variables_setup_test(self):
        tmp_folder1 = temp_folder()
        tmp_folder2 = temp_folder()
        save(os.path.join(tmp_folder1, "include1", "file.h"), "")
        save(os.path.join(tmp_folder2, "include2", "file.h"), "")
        save(os.path.join(tmp_folder1, "lib1", "file.a"), "")
        save(os.path.join(tmp_folder2, "lib2", "file.a"), "")
        save(os.path.join(tmp_folder1, "bin1", "file.bin"), "")
        save(os.path.join(tmp_folder2, "bin2", "file.bin"), "")

        conanfile = ConanFile(None, None)
        conanfile.initialize(Settings({}), EnvValues())
        ref = ConanFileReference.loads("MyPkg1/0.1@lasote/stables")
        cpp_info = CppInfo(tmp_folder1)
        cpp_info.defines = ["MYDEFINE1"]
        cpp_info.includedirs = ['include1']
        cpp_info.libdirs = ['lib1']
        cpp_info.libs = ['libfoo']
        cpp_info.bindirs = ['bin1']
        cpp_info.version = "0.1"
        cpp_info.cflags = ['-fgimple']
        cpp_info.cppflags = ['-fdollars-in-identifiers']
        cpp_info.sharedlinkflags = ['-framework Cocoa']
        cpp_info.exelinkflags = ['-framework QuartzCore']
        conanfile.deps_cpp_info.update(cpp_info, ref.name)
        ref = ConanFileReference.loads("MyPkg2/3.2.3@lasote/stables")
        cpp_info = CppInfo(tmp_folder2)
        cpp_info.defines = ["MYDEFINE2"]
        cpp_info.includedirs = ['include2']
        cpp_info.libdirs = ['lib2']
        cpp_info.libs = ['libbar']
        cpp_info.bindirs = ['bin2']
        cpp_info.version = "3.2.3"
        cpp_info.cflags = ['-fno-asm']
        cpp_info.cppflags = ['-pthread']
        cpp_info.sharedlinkflags = ['-framework AudioFoundation']
        cpp_info.exelinkflags = ['-framework VideoToolbox']
        conanfile.deps_cpp_info.update(cpp_info, ref.name)
        generator = MakeGenerator(conanfile)
        content = generator.content

        content_template = """
CONAN_ROOT_MYPKG1 ?=  \\
{conan_root_mypkg1}

CONAN_SYSROOT_MYPKG1 ?=  \\


CONAN_INCLUDE_PATHS_MYPKG1 +=  \\
{conan_include_paths_mypkg1}

CONAN_LIB_PATHS_MYPKG1 +=  \\
{conan_lib_paths_mypkg1}

CONAN_BIN_PATHS_MYPKG1 +=  \\
{conan_bin_paths_mypkg1}

CONAN_BUILD_PATHS_MYPKG1 +=  \\
{conan_build_paths_mypkg1}

CONAN_RES_PATHS_MYPKG1 +=  \\


CONAN_LIBS_MYPKG1 +=  \\
libfoo

CONAN_DEFINES_MYPKG1 +=  \\
MYDEFINE1

CONAN_CFLAGS_MYPKG1 +=  \\
-fgimple

CONAN_CPPFLAGS_MYPKG1 +=  \\
-fdollars-in-identifiers

CONAN_SHAREDLINKFLAGS_MYPKG1 +=  \\
-framework Cocoa

CONAN_EXELINKFLAGS_MYPKG1 +=  \\
-framework QuartzCore

CONAN_ROOT_MYPKG2 ?=  \\
{conan_root_mypkg2}

CONAN_SYSROOT_MYPKG2 ?=  \\


CONAN_INCLUDE_PATHS_MYPKG2 +=  \\
{conan_include_paths_mypkg2}

CONAN_LIB_PATHS_MYPKG2 +=  \\
{conan_lib_paths_mypkg2}

CONAN_BIN_PATHS_MYPKG2 +=  \\
{conan_bin_paths_mypkg2}

CONAN_BUILD_PATHS_MYPKG2 +=  \\
{conan_build_paths_mypkg2}

CONAN_RES_PATHS_MYPKG2 +=  \\


CONAN_LIBS_MYPKG2 +=  \\
libbar

CONAN_DEFINES_MYPKG2 +=  \\
MYDEFINE2

CONAN_CFLAGS_MYPKG2 +=  \\
-fno-asm

CONAN_CPPFLAGS_MYPKG2 +=  \\
-pthread

CONAN_SHAREDLINKFLAGS_MYPKG2 +=  \\
-framework AudioFoundation

CONAN_EXELINKFLAGS_MYPKG2 +=  \\
-framework VideoToolbox

CONAN_ROOTPATH +=  \\
$(CONAN_ROOTPATH_MYPKG1) \\
$(CONAN_ROOTPATH_MYPKG2)

CONAN_SYSROOT +=  \\
$(CONAN_SYSROOT_MYPKG1) \\
$(CONAN_SYSROOT_MYPKG2)

CONAN_INCLUDE_PATHS +=  \\
$(CONAN_INCLUDE_PATHS_MYPKG1) \\
$(CONAN_INCLUDE_PATHS_MYPKG2)

CONAN_LIB_PATHS +=  \\
$(CONAN_LIB_PATHS_MYPKG1) \\
$(CONAN_LIB_PATHS_MYPKG2)

CONAN_BIN_PATHS +=  \\
$(CONAN_BIN_PATHS_MYPKG1) \\
$(CONAN_BIN_PATHS_MYPKG2)

CONAN_BUILD_PATHS +=  \\
$(CONAN_BUILD_PATHS_MYPKG1) \\
$(CONAN_BUILD_PATHS_MYPKG2)

CONAN_RES_PATHS +=  \\
$(CONAN_RES_PATHS_MYPKG1) \\
$(CONAN_RES_PATHS_MYPKG2)

CONAN_LIBS +=  \\
$(CONAN_LIBS_MYPKG1) \\
$(CONAN_LIBS_MYPKG2)

CONAN_DEFINES +=  \\
$(CONAN_DEFINES_MYPKG1) \\
$(CONAN_DEFINES_MYPKG2)

CONAN_CFLAGS +=  \\
$(CONAN_CFLAGS_MYPKG1) \\
$(CONAN_CFLAGS_MYPKG2)

CONAN_CPPFLAGS +=  \\
$(CONAN_CPPFLAGS_MYPKG1) \\
$(CONAN_CPPFLAGS_MYPKG2)

CONAN_SHAREDLINKFLAGS +=  \\
$(CONAN_SHAREDLINKFLAGS_MYPKG1) \\
$(CONAN_SHAREDLINKFLAGS_MYPKG2)

CONAN_EXELINKFLAGS +=  \\
$(CONAN_EXELINKFLAGS_MYPKG1) \\
$(CONAN_EXELINKFLAGS_MYPKG2)
"""
        root1 = tmp_folder1.replace('\\', '/')
        root2 = tmp_folder2.replace('\\', '/')

        inc1 = os.path.join(tmp_folder1, 'include1').replace('\\', '/')
        inc2 = os.path.join(tmp_folder2, 'include2').replace('\\', '/')

        lib1 = os.path.join(tmp_folder1, 'lib1').replace('\\', '/')
        lib2 = os.path.join(tmp_folder2, 'lib2').replace('\\', '/')

        bin1 = os.path.join(tmp_folder1, 'bin1').replace('\\', '/')
        bin2 = os.path.join(tmp_folder2, 'bin2').replace('\\', '/')

        expected_content = content_template.format(conan_root_mypkg1=root1,
                                                   conan_include_paths_mypkg1=inc1,
                                                   conan_lib_paths_mypkg1=lib1,
                                                   conan_bin_paths_mypkg1=bin1,
                                                   conan_build_paths_mypkg1=root1 + "/",
                                                   conan_root_mypkg2=root2,
                                                   conan_include_paths_mypkg2=inc2,
                                                   conan_lib_paths_mypkg2=lib2,
                                                   conan_bin_paths_mypkg2=bin2,
                                                   conan_build_paths_mypkg2=root2 + "/")
        self.assertIn(expected_content, content)

    @unittest.skipUnless(platform.system() == "Linux", "Requires make")
    def integration_test(self):
        client = TestClient(path_with_spaces=False)
        client.run("new myhello/1.0.0 --sources")
        conanfile_path = os.path.join(client.current_folder, "conanfile.py")
        replace_in_file(conanfile_path, "{\"shared\": [True, False]}",
                        "{\"shared\": [True, False], \"fPIC\": [True, False]}")
        replace_in_file(conanfile_path, "\"shared=False\"", "\"shared=False\", \"fPIC=True\"")
        client.run("create . danimtb/testing")
        hellowrapper_include = """
#pragma once

void hellowrapper();
"""
        hellowrapper_impl = """
#include "hello.h"

#include "hellowrapper.h"

void hellowrapper(){
    hello();
}
"""
        makefile = """
include conanbuildinfo.mak

#----------------------------------------
#     Make variables for a sample App
#----------------------------------------

INCLUDE_PATHS = \
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
CXXFLAGS            += $(CONAN_CPPFLAGS)
CPPFLAGS            += $(addprefix -I, $(INCLUDE_PATHS) $(CONAN_INCLUDE_PATHS))
CPPFLAGS            += $(addprefix -D, $(CONAN_DEFINES))
LDFLAGS             += $(addprefix -L, $(CONAN_LIB_PATHS))
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

%.o                     :   $(CXX_SRCS)
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
CXXFLAGS            += $(CONAN_CPPFLAGS)
CPPFLAGS            += $(addprefix -I, $(CONAN_INCLUDE_PATHS))
CPPFLAGS            += $(addprefix -D, $(CONAN_DEFINES))
LDFLAGS             += $(addprefix -L, $(CONAN_LIB_PATHS))
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

%.o                     :   $(CXX_SRCS)
	$(COMPILE_CXX_COMMAND)
"""
        conanfile_txt = """
[requires]
hellowrapper/1.0@danimtb/testing

[generators]
make
"""
        client.save({"src/main.cpp": main, "Makefile": makefile, "conanfile.txt": conanfile_txt},
                    clean_first=True)
        with chdir(client.current_folder):
            client.run("install .")
            client.runner("make exe")
            client.runner("./main")
            self.assertIn("Hello World Release!", client.out)

            # Test it also builds with shared lib
            client.run("install . -o hellowrapper:shared=True")
            client.runner("rm main main.o")
            client.runner("make exe")
            client.runner("ldd main")
            self.assertIn("libhellowrapper.so", client.out)
