import re
import os
import unittest
import textwrap

from conans.client.generators import MakeGenerator
from conans.model.build_info import CppInfo
from conans.model.conan_file import ConanFile
from conans.model.env_info import EnvValues
from conans.model.ref import ConanFileReference
from conans.test.utils.test_files import temp_folder
from conans.test.utils.mocks import TestBufferConanOutput
from conans.util.files import save

from parameterized.parameterized import parameterized


class _MockSettings(object):
    build_type = None
    compiler = None
    os_ = None
    os_build = None
    fields = []

    def __init__(self, compiler, os_):
        self.compiler = compiler
        self.os_ = os_
        self.os_build = os_

    def constraint(self, _):
        return self

    def get_safe(self, name):
        if name == "compiler":
            return self.compiler
        if name == "os":
            return self.os_

        return None

    def items(self):
        return {}


EXPECTED_OUT_1 = textwrap.dedent("""
#-------------------------------------------------------------------#
#             Makefile variables from Conan Dependencies            #
#-------------------------------------------------------------------#

CONAN_ROOT_MYPKG1 ?=  \\
/tmp1

CONAN_SYSROOT_MYPKG1 ?=  \\


CONAN_RPATHFLAGS_MYPKG1 +=  \\
-Wl,-rpath="/tmp1/lib1"

CONAN_INCLUDE_DIRS_MYPKG1 +=  \\
/tmp1/include1

CONAN_LIB_DIRS_MYPKG1 +=  \\
/tmp1/lib1

CONAN_BIN_DIRS_MYPKG1 +=  \\
/tmp1/bin1

CONAN_BUILD_DIRS_MYPKG1 +=  \\
/tmp1/

CONAN_RES_DIRS_MYPKG1 +=  \\


CONAN_LIBS_MYPKG1 +=  \\
libfoo

CONAN_SYSTEM_LIBS_MYPKG1 +=  \\
system_lib1

CONAN_DEFINES_MYPKG1 +=  \\
MYDEFINE1

CONAN_CFLAGS_MYPKG1 +=  \\
-fgimple

CONAN_CXXFLAGS_MYPKG1 +=  \\
-fdollars-in-identifiers

CONAN_SHAREDLINKFLAGS_MYPKG1 +=  \\
-framework Cocoa

CONAN_EXELINKFLAGS_MYPKG1 +=  \\
-framework QuartzCore

CONAN_FRAMEWORKS_MYPKG1 +=  \\
AudioUnit

CONAN_FRAMEWORK_PATHS_MYPKG1 +=  \\
/tmp1/SystemFrameworks

CONAN_ROOT_MYPKG2 ?=  \\
/tmp2

CONAN_SYSROOT_MYPKG2 ?=  \\


CONAN_RPATHFLAGS_MYPKG2 +=  \\
-Wl,-rpath="/tmp2/lib2"

CONAN_INCLUDE_DIRS_MYPKG2 +=  \\
/tmp2/include2

CONAN_LIB_DIRS_MYPKG2 +=  \\
/tmp2/lib2

CONAN_BIN_DIRS_MYPKG2 +=  \\
/tmp2/bin2

CONAN_BUILD_DIRS_MYPKG2 +=  \\
/tmp2/

CONAN_RES_DIRS_MYPKG2 +=  \\


CONAN_LIBS_MYPKG2 +=  \\
libbar

CONAN_SYSTEM_LIBS_MYPKG2 +=  \\
system_lib2

CONAN_DEFINES_MYPKG2 +=  \\
MYDEFINE2

CONAN_CFLAGS_MYPKG2 +=  \\
-fno-asm

CONAN_CXXFLAGS_MYPKG2 +=  \\
-pthread

CONAN_SHAREDLINKFLAGS_MYPKG2 +=  \\
-framework AudioFoundation

CONAN_EXELINKFLAGS_MYPKG2 +=  \\
-framework VideoToolbox

CONAN_FRAMEWORKS_MYPKG2 +=  \\


CONAN_FRAMEWORK_PATHS_MYPKG2 +=  \\


CONAN_ROOTPATH +=  \\
$(CONAN_ROOTPATH_MYPKG1) \\
$(CONAN_ROOTPATH_MYPKG2)

CONAN_SYSROOT +=  \\
$(CONAN_SYSROOT_MYPKG1) \\
$(CONAN_SYSROOT_MYPKG2)

CONAN_RPATHFLAGS +=  \\
$(CONAN_RPATHFLAGS_MYPKG1) \\
$(CONAN_RPATHFLAGS_MYPKG2)

CONAN_INCLUDE_DIRS +=  \\
$(CONAN_INCLUDE_DIRS_MYPKG1) \\
$(CONAN_INCLUDE_DIRS_MYPKG2)

CONAN_LIB_DIRS +=  \\
$(CONAN_LIB_DIRS_MYPKG1) \\
$(CONAN_LIB_DIRS_MYPKG2)

CONAN_BIN_DIRS +=  \\
$(CONAN_BIN_DIRS_MYPKG1) \\
$(CONAN_BIN_DIRS_MYPKG2)

CONAN_BUILD_DIRS +=  \\
$(CONAN_BUILD_DIRS_MYPKG1) \\
$(CONAN_BUILD_DIRS_MYPKG2)

CONAN_RES_DIRS +=  \\
$(CONAN_RES_DIRS_MYPKG1) \\
$(CONAN_RES_DIRS_MYPKG2)

CONAN_LIBS +=  \\
$(CONAN_LIBS_MYPKG1) \\
$(CONAN_LIBS_MYPKG2)

CONAN_DEFINES +=  \\
$(CONAN_DEFINES_MYPKG1) \\
$(CONAN_DEFINES_MYPKG2)

CONAN_CFLAGS +=  \\
$(CONAN_CFLAGS_MYPKG1) \\
$(CONAN_CFLAGS_MYPKG2)

CONAN_CXXFLAGS +=  \\
$(CONAN_CXXFLAGS_MYPKG1) \\
$(CONAN_CXXFLAGS_MYPKG2)

CONAN_SHAREDLINKFLAGS +=  \\
$(CONAN_SHAREDLINKFLAGS_MYPKG1) \\
$(CONAN_SHAREDLINKFLAGS_MYPKG2)

CONAN_EXELINKFLAGS +=  \\
$(CONAN_EXELINKFLAGS_MYPKG1) \\
$(CONAN_EXELINKFLAGS_MYPKG2)

CONAN_FRAMEWORKS +=  \\
$(CONAN_FRAMEWORKS_MYPKG1) \\
$(CONAN_FRAMEWORKS_MYPKG2)

CONAN_FRAMEWORK_PATHS +=  \\
$(CONAN_FRAMEWORK_PATHS_MYPKG1) \\
$(CONAN_FRAMEWORK_PATHS_MYPKG2)

CONAN_SYSTEM_LIBS +=  \\
$(CONAN_SYSTEM_LIBS_MYPKG1) \\
$(CONAN_SYSTEM_LIBS_MYPKG2)


CONAN_CPPFLAGS      += $(addprefix -I,$(CONAN_INCLUDE_DIRS))
CONAN_CPPFLAGS      += $(addprefix -D,$(CONAN_DEFINES))
CONAN_LDFLAGS       += $(addprefix -L,$(CONAN_LIB_DIRS))
CONAN_LDFLAGS       += $(CONAN_RPATHFLAGS)
CONAN_LDLIBS        += $(addprefix -l,$(CONAN_SYSTEM_LIBS))
CONAN_LDLIBS        += $(addprefix -l,$(CONAN_LIBS))

# Call the following function to have Conan variables added to standard variables
# 1 optional parameter : type of target being built : EXE or SHARED
# Appends either CONAN_EXELINKFLAGS or CONAN_SHAREDLINKFLAGS to LDFLAGS
# Example 1:  $(call CONAN_BASIC_SETUP)
# Example 2:  $(call CONAN_BASIC_SETUP, EXE)
# Example 3:  $(call CONAN_BASIC_SETUP, SHARED)

CONAN_BASIC_SETUP = \\
    $(eval CFLAGS   += $(CONAN_CFLAGS)) ; \\
    $(eval CXXFLAGS += $(CONAN_CXXFLAGS)) ; \\
    $(eval CPPFLAGS += $(CONAN_CPPFLAGS)) ; \\
    $(eval LDFLAGS  += $(CONAN_LDFLAGS)) ; \\
    $(eval LDFLAGS  += $(CONAN_$(1)LINKFLAGS)) ; \\
    $(eval LDLIBS   += $(CONAN_LDLIBS)) ;



#-------------------------------------------------------------------#

""")

EXPECTED_OUT_2 = textwrap.dedent("""
#-------------------------------------------------------------------#
#             Makefile variables from Conan Dependencies            #
#-------------------------------------------------------------------#

CONAN_ROOT_MYPKG1 ?=  \\
/tmp1

CONAN_SYSROOT_MYPKG1 ?=  \\


CONAN_RPATHFLAGS_MYPKG1 +=  \\
-Wl,-rpath="/tmp1/lib1"

CONAN_INCLUDE_DIRS_MYPKG1 +=  \\
/tmp1/include1

CONAN_LIB_DIRS_MYPKG1 +=  \\
/tmp1/lib1

CONAN_BIN_DIRS_MYPKG1 +=  \\
/tmp1/bin1

CONAN_BUILD_DIRS_MYPKG1 +=  \\
/tmp1/

CONAN_RES_DIRS_MYPKG1 +=  \\


CONAN_LIBS_MYPKG1 +=  \\
libfoo

CONAN_SYSTEM_LIBS_MYPKG1 +=  \\
system_lib1

CONAN_DEFINES_MYPKG1 +=  \\
MYDEFINE1

CONAN_CFLAGS_MYPKG1 +=  \\
-fgimple

CONAN_CXXFLAGS_MYPKG1 +=  \\
-fdollars-in-identifiers

CONAN_SHAREDLINKFLAGS_MYPKG1 +=  \\
-framework Cocoa

CONAN_EXELINKFLAGS_MYPKG1 +=  \\
-framework QuartzCore

CONAN_FRAMEWORKS_MYPKG1 +=  \\
AudioUnit

CONAN_FRAMEWORK_PATHS_MYPKG1 +=  \\
/tmp1/SystemFrameworks

CONAN_ROOT_MYPKG2 ?=  \\
/tmp2

CONAN_SYSROOT_MYPKG2 ?=  \\


CONAN_RPATHFLAGS_MYPKG2 +=  \\
-Wl,-rpath="/tmp2/lib2"

CONAN_INCLUDE_DIRS_MYPKG2 +=  \\
/tmp2/include2

CONAN_LIB_DIRS_MYPKG2 +=  \\
/tmp2/lib2

CONAN_BIN_DIRS_MYPKG2 +=  \\
/tmp2/bin2

CONAN_BUILD_DIRS_MYPKG2 +=  \\
/tmp2/

CONAN_RES_DIRS_MYPKG2 +=  \\


CONAN_LIBS_MYPKG2 +=  \\
libbar

CONAN_SYSTEM_LIBS_MYPKG2 +=  \\
system_lib2

CONAN_DEFINES_MYPKG2 +=  \\
MYDEFINE2

CONAN_CFLAGS_MYPKG2 +=  \\
-fno-asm

CONAN_CXXFLAGS_MYPKG2 +=  \\
-pthread

CONAN_SHAREDLINKFLAGS_MYPKG2 +=  \\
-framework AudioFoundation

CONAN_EXELINKFLAGS_MYPKG2 +=  \\
-framework VideoToolbox

CONAN_FRAMEWORKS_MYPKG2 +=  \\


CONAN_FRAMEWORK_PATHS_MYPKG2 +=  \\


CONAN_ROOTPATH +=  \\
$(CONAN_ROOTPATH_MYPKG1) \\
$(CONAN_ROOTPATH_MYPKG2)

CONAN_SYSROOT +=  \\
$(CONAN_SYSROOT_MYPKG1) \\
$(CONAN_SYSROOT_MYPKG2)

CONAN_RPATHFLAGS +=  \\
$(CONAN_RPATHFLAGS_MYPKG1) \\
$(CONAN_RPATHFLAGS_MYPKG2)

CONAN_INCLUDE_DIRS +=  \\
$(CONAN_INCLUDE_DIRS_MYPKG1) \\
$(CONAN_INCLUDE_DIRS_MYPKG2)

CONAN_LIB_DIRS +=  \\
$(CONAN_LIB_DIRS_MYPKG1) \\
$(CONAN_LIB_DIRS_MYPKG2)

CONAN_BIN_DIRS +=  \\
$(CONAN_BIN_DIRS_MYPKG1) \\
$(CONAN_BIN_DIRS_MYPKG2)

CONAN_BUILD_DIRS +=  \\
$(CONAN_BUILD_DIRS_MYPKG1) \\
$(CONAN_BUILD_DIRS_MYPKG2)

CONAN_RES_DIRS +=  \\
$(CONAN_RES_DIRS_MYPKG1) \\
$(CONAN_RES_DIRS_MYPKG2)

CONAN_LIBS +=  \\
$(CONAN_LIBS_MYPKG1) \\
$(CONAN_LIBS_MYPKG2)

CONAN_DEFINES +=  \\
$(CONAN_DEFINES_MYPKG1) \\
$(CONAN_DEFINES_MYPKG2)

CONAN_CFLAGS +=  \\
$(CONAN_CFLAGS_MYPKG1) \\
$(CONAN_CFLAGS_MYPKG2)

CONAN_CXXFLAGS +=  \\
$(CONAN_CXXFLAGS_MYPKG1) \\
$(CONAN_CXXFLAGS_MYPKG2)

CONAN_SHAREDLINKFLAGS +=  \\
$(CONAN_SHAREDLINKFLAGS_MYPKG1) \\
$(CONAN_SHAREDLINKFLAGS_MYPKG2)

CONAN_EXELINKFLAGS +=  \\
$(CONAN_EXELINKFLAGS_MYPKG1) \\
$(CONAN_EXELINKFLAGS_MYPKG2)

CONAN_FRAMEWORKS +=  \\
$(CONAN_FRAMEWORKS_MYPKG1) \\
$(CONAN_FRAMEWORKS_MYPKG2)

CONAN_FRAMEWORK_PATHS +=  \\
$(CONAN_FRAMEWORK_PATHS_MYPKG1) \\
$(CONAN_FRAMEWORK_PATHS_MYPKG2)

CONAN_SYSTEM_LIBS +=  \\
$(CONAN_SYSTEM_LIBS_MYPKG1) \\
$(CONAN_SYSTEM_LIBS_MYPKG2)


CONAN_CPPFLAGS      += $(addprefix -I,$(CONAN_INCLUDE_DIRS))
CONAN_CPPFLAGS      += $(addprefix -D,$(CONAN_DEFINES))
CONAN_LDFLAGS       += $(addprefix -L,$(CONAN_LIB_DIRS))
CONAN_LDFLAGS       += $(CONAN_RPATHFLAGS)
CONAN_LDLIBS        += $(addprefix -l,$(CONAN_SYSTEM_LIBS))
CONAN_LDLIBS        += $(addprefix -l,$(CONAN_LIBS))

# Call the following function to have Conan variables added to standard variables
# 1 optional parameter : type of target being built : EXE or SHARED
# Appends either CONAN_EXELINKFLAGS or CONAN_SHAREDLINKFLAGS to LDFLAGS
# Example 1:  $(call CONAN_BASIC_SETUP)
# Example 2:  $(call CONAN_BASIC_SETUP, EXE)
# Example 3:  $(call CONAN_BASIC_SETUP, SHARED)

CONAN_BASIC_SETUP = \\
    $(eval CFLAGS   += $(CONAN_CFLAGS)) ; \\
    $(eval CXXFLAGS += $(CONAN_CXXFLAGS)) ; \\
    $(eval CPPFLAGS += $(CONAN_CPPFLAGS)) ; \\
    $(eval LDFLAGS  += $(CONAN_LDFLAGS)) ; \\
    $(eval LDFLAGS  += $(CONAN_$(1)LINKFLAGS)) ; \\
    $(eval LDLIBS   += $(CONAN_LDLIBS)) ;



#-------------------------------------------------------------------#

""")

EXPECTED_OUT_3 = textwrap.dedent("""
#-------------------------------------------------------------------#
#             Makefile variables from Conan Dependencies            #
#-------------------------------------------------------------------#

CONAN_ROOT_MYPKG1 ?=  \\
/tmp1

CONAN_SYSROOT_MYPKG1 ?=  \\


CONAN_RPATHFLAGS_MYPKG1 +=  \\
-Wl,-rpath,"/tmp1/lib1"

CONAN_INCLUDE_DIRS_MYPKG1 +=  \\
/tmp1/include1

CONAN_LIB_DIRS_MYPKG1 +=  \\
/tmp1/lib1

CONAN_BIN_DIRS_MYPKG1 +=  \\
/tmp1/bin1

CONAN_BUILD_DIRS_MYPKG1 +=  \\
/tmp1/

CONAN_RES_DIRS_MYPKG1 +=  \\


CONAN_LIBS_MYPKG1 +=  \\
libfoo

CONAN_SYSTEM_LIBS_MYPKG1 +=  \\
system_lib1

CONAN_DEFINES_MYPKG1 +=  \\
MYDEFINE1

CONAN_CFLAGS_MYPKG1 +=  \\
-fgimple

CONAN_CXXFLAGS_MYPKG1 +=  \\
-fdollars-in-identifiers

CONAN_SHAREDLINKFLAGS_MYPKG1 +=  \\
-framework Cocoa

CONAN_EXELINKFLAGS_MYPKG1 +=  \\
-framework QuartzCore

CONAN_FRAMEWORKS_MYPKG1 +=  \\
AudioUnit

CONAN_FRAMEWORK_PATHS_MYPKG1 +=  \\
/tmp1/SystemFrameworks

CONAN_ROOT_MYPKG2 ?=  \\
/tmp2

CONAN_SYSROOT_MYPKG2 ?=  \\


CONAN_RPATHFLAGS_MYPKG2 +=  \\
-Wl,-rpath,"/tmp2/lib2"

CONAN_INCLUDE_DIRS_MYPKG2 +=  \\
/tmp2/include2

CONAN_LIB_DIRS_MYPKG2 +=  \\
/tmp2/lib2

CONAN_BIN_DIRS_MYPKG2 +=  \\
/tmp2/bin2

CONAN_BUILD_DIRS_MYPKG2 +=  \\
/tmp2/

CONAN_RES_DIRS_MYPKG2 +=  \\


CONAN_LIBS_MYPKG2 +=  \\
libbar

CONAN_SYSTEM_LIBS_MYPKG2 +=  \\
system_lib2

CONAN_DEFINES_MYPKG2 +=  \\
MYDEFINE2

CONAN_CFLAGS_MYPKG2 +=  \\
-fno-asm

CONAN_CXXFLAGS_MYPKG2 +=  \\
-pthread

CONAN_SHAREDLINKFLAGS_MYPKG2 +=  \\
-framework AudioFoundation

CONAN_EXELINKFLAGS_MYPKG2 +=  \\
-framework VideoToolbox

CONAN_FRAMEWORKS_MYPKG2 +=  \\


CONAN_FRAMEWORK_PATHS_MYPKG2 +=  \\


CONAN_ROOTPATH +=  \\
$(CONAN_ROOTPATH_MYPKG1) \\
$(CONAN_ROOTPATH_MYPKG2)

CONAN_SYSROOT +=  \\
$(CONAN_SYSROOT_MYPKG1) \\
$(CONAN_SYSROOT_MYPKG2)

CONAN_RPATHFLAGS +=  \\
$(CONAN_RPATHFLAGS_MYPKG1) \\
$(CONAN_RPATHFLAGS_MYPKG2)

CONAN_INCLUDE_DIRS +=  \\
$(CONAN_INCLUDE_DIRS_MYPKG1) \\
$(CONAN_INCLUDE_DIRS_MYPKG2)

CONAN_LIB_DIRS +=  \\
$(CONAN_LIB_DIRS_MYPKG1) \\
$(CONAN_LIB_DIRS_MYPKG2)

CONAN_BIN_DIRS +=  \\
$(CONAN_BIN_DIRS_MYPKG1) \\
$(CONAN_BIN_DIRS_MYPKG2)

CONAN_BUILD_DIRS +=  \\
$(CONAN_BUILD_DIRS_MYPKG1) \\
$(CONAN_BUILD_DIRS_MYPKG2)

CONAN_RES_DIRS +=  \\
$(CONAN_RES_DIRS_MYPKG1) \\
$(CONAN_RES_DIRS_MYPKG2)

CONAN_LIBS +=  \\
$(CONAN_LIBS_MYPKG1) \\
$(CONAN_LIBS_MYPKG2)

CONAN_DEFINES +=  \\
$(CONAN_DEFINES_MYPKG1) \\
$(CONAN_DEFINES_MYPKG2)

CONAN_CFLAGS +=  \\
$(CONAN_CFLAGS_MYPKG1) \\
$(CONAN_CFLAGS_MYPKG2)

CONAN_CXXFLAGS +=  \\
$(CONAN_CXXFLAGS_MYPKG1) \\
$(CONAN_CXXFLAGS_MYPKG2)

CONAN_SHAREDLINKFLAGS +=  \\
$(CONAN_SHAREDLINKFLAGS_MYPKG1) \\
$(CONAN_SHAREDLINKFLAGS_MYPKG2)

CONAN_EXELINKFLAGS +=  \\
$(CONAN_EXELINKFLAGS_MYPKG1) \\
$(CONAN_EXELINKFLAGS_MYPKG2)

CONAN_FRAMEWORKS +=  \\
$(CONAN_FRAMEWORKS_MYPKG1) \\
$(CONAN_FRAMEWORKS_MYPKG2)

CONAN_FRAMEWORK_PATHS +=  \\
$(CONAN_FRAMEWORK_PATHS_MYPKG1) \\
$(CONAN_FRAMEWORK_PATHS_MYPKG2)

CONAN_SYSTEM_LIBS +=  \\
$(CONAN_SYSTEM_LIBS_MYPKG1) \\
$(CONAN_SYSTEM_LIBS_MYPKG2)


CONAN_CPPFLAGS      += $(addprefix -I,$(CONAN_INCLUDE_DIRS))
CONAN_CPPFLAGS      += $(addprefix -D,$(CONAN_DEFINES))
CONAN_LDFLAGS       += $(addprefix -L,$(CONAN_LIB_DIRS))
CONAN_LDFLAGS       += $(CONAN_RPATHFLAGS)
CONAN_LDLIBS        += $(addprefix -l,$(CONAN_SYSTEM_LIBS))
CONAN_LDLIBS        += $(addprefix -l,$(CONAN_LIBS))

# Call the following function to have Conan variables added to standard variables
# 1 optional parameter : type of target being built : EXE or SHARED
# Appends either CONAN_EXELINKFLAGS or CONAN_SHAREDLINKFLAGS to LDFLAGS
# Example 1:  $(call CONAN_BASIC_SETUP)
# Example 2:  $(call CONAN_BASIC_SETUP, EXE)
# Example 3:  $(call CONAN_BASIC_SETUP, SHARED)

CONAN_BASIC_SETUP = \\
    $(eval CFLAGS   += $(CONAN_CFLAGS)) ; \\
    $(eval CXXFLAGS += $(CONAN_CXXFLAGS)) ; \\
    $(eval CPPFLAGS += $(CONAN_CPPFLAGS)) ; \\
    $(eval LDFLAGS  += $(CONAN_LDFLAGS)) ; \\
    $(eval LDFLAGS  += $(CONAN_$(1)LINKFLAGS)) ; \\
    $(eval LDLIBS   += $(CONAN_LDLIBS)) ;



#-------------------------------------------------------------------#

""")


class MakeGeneratorTest(unittest.TestCase):
    @parameterized.expand([
        ("gcc", "Linux", False, EXPECTED_OUT_1),
        ("gcc", "Linux", True, EXPECTED_OUT_2),
        ("gcc", "Macos", False, EXPECTED_OUT_3),
    ])
    def variables_setup_test(self, compiler_, os_, shared_, expected):
        tmp_folder1 = temp_folder()
        tmp_folder2 = temp_folder()
        save(os.path.join(tmp_folder1, "include1", "file.h"), "")
        save(os.path.join(tmp_folder2, "include2", "file.h"), "")
        save(os.path.join(tmp_folder1, "lib1", "file.a"), "")
        save(os.path.join(tmp_folder2, "lib2", "file.a"), "")
        save(os.path.join(tmp_folder1, "bin1", "file.bin"), "")
        save(os.path.join(tmp_folder2, "bin2", "file.bin"), "")
        save(os.path.join(tmp_folder1, "SystemFrameworks", "file.bin"), "")

        settings_mock = _MockSettings(compiler=compiler_, os_=os_)
        conanfile = ConanFile(TestBufferConanOutput(), None)
        conanfile.options = {"shared": [True, False]}
        conanfile.default_options = {"shared": shared_}
        conanfile.initialize(settings_mock, EnvValues())
        ref = ConanFileReference.loads("MyPkg1/0.1@lasote/stables")
        cpp_info = CppInfo(ref.name, tmp_folder1)
        cpp_info.defines = ["MYDEFINE1"]
        cpp_info.includedirs = ['include1']
        cpp_info.libdirs = ['lib1']
        cpp_info.libs = ['libfoo']
        cpp_info.bindirs = ['bin1']
        cpp_info.version = "0.1"
        cpp_info.cflags = ['-fgimple']
        cpp_info.cxxflags = ['-fdollars-in-identifiers']
        cpp_info.sharedlinkflags = ['-framework Cocoa']
        cpp_info.exelinkflags = ['-framework QuartzCore']
        cpp_info.frameworks = ['AudioUnit']
        cpp_info.frameworkdirs = ['SystemFrameworks']
        cpp_info.system_libs = ["system_lib1"]
        conanfile.deps_cpp_info.add(ref.name, cpp_info)
        ref = ConanFileReference.loads("MyPkg2/3.2.3@lasote/stables")
        cpp_info = CppInfo(ref.name, tmp_folder2)
        cpp_info.defines = ["MYDEFINE2"]
        cpp_info.includedirs = ['include2']
        cpp_info.libdirs = ['lib2']
        cpp_info.libs = ['libbar']
        cpp_info.bindirs = ['bin2']
        cpp_info.version = "3.2.3"
        cpp_info.cflags = ['-fno-asm']
        cpp_info.cxxflags = ['-pthread']
        cpp_info.sharedlinkflags = ['-framework AudioFoundation']
        cpp_info.exelinkflags = ['-framework VideoToolbox']
        cpp_info.system_libs = ["system_lib2"]
        conanfile.deps_cpp_info.add(ref.name, cpp_info)
        generator = MakeGenerator(conanfile)
        content = generator.content
        self.maxDiff = None
        sanitized_content = content\
            .replace(tmp_folder1, "/tmp1")\
            .replace(tmp_folder2, "/tmp2")
        self.assertIn(expected, sanitized_content)
