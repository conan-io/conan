import os

from mock import Mock

from conans.client.generators import MakeGenerator
from conans.model.build_info import CppInfo
from conans.model.conan_file import ConanFile
from conans.model.env_info import EnvValues
from conans.model.ref import ConanFileReference
from conans.model.settings import Settings
from conans.test.utils.test_files import temp_folder
from conans.util.files import save


def test_make_generator():
    tmp_folder1 = temp_folder()
    tmp_folder2 = temp_folder()
    save(os.path.join(tmp_folder1, "include1", "file.h"), "")
    save(os.path.join(tmp_folder2, "include2", "file.h"), "")
    save(os.path.join(tmp_folder1, "lib1", "file.a"), "")
    save(os.path.join(tmp_folder2, "lib2", "file.a"), "")
    save(os.path.join(tmp_folder1, "bin1", "file.bin"), "")
    save(os.path.join(tmp_folder2, "bin2", "file.bin"), "")
    save(os.path.join(tmp_folder1, "SystemFrameworks", "file.bin"), "")

    conanfile = ConanFile(Mock(), None)
    conanfile.initialize(Settings({}), EnvValues())
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

    content_template = """
CONAN_ROOT_MYPKG1 ?=  \\
{conan_root_mypkg1}

CONAN_SYSROOT_MYPKG1 ?=  \\


CONAN_INCLUDE_DIRS_MYPKG1 +=  \\
{conan_include_dirs_mypkg1}

CONAN_LIB_DIRS_MYPKG1 +=  \\
{conan_lib_dirs_mypkg1}

CONAN_BIN_DIRS_MYPKG1 +=  \\
{conan_bin_dirs_mypkg1}

CONAN_BUILD_DIRS_MYPKG1 +=  \\
{conan_build_dirs_mypkg1}/

CONAN_RES_DIRS_MYPKG1 +=

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
{conan_framework_dirs_mypkg1}/SystemFrameworks

CONAN_ROOT_MYPKG2 ?=  \\
{conan_root_mypkg2}

CONAN_SYSROOT_MYPKG2 ?=  \\


CONAN_INCLUDE_DIRS_MYPKG2 +=  \\
{conan_include_dirs_mypkg2}

CONAN_LIB_DIRS_MYPKG2 +=  \\
{conan_lib_dirs_mypkg2}

CONAN_BIN_DIRS_MYPKG2 +=  \\
{conan_bin_dirs_mypkg2}

CONAN_BUILD_DIRS_MYPKG2 +=  \\
{conan_build_dirs_mypkg2}/

CONAN_RES_DIRS_MYPKG2 +=

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

CONAN_FRAMEWORKS_MYPKG2 +=

CONAN_FRAMEWORK_PATHS_MYPKG2 +=

CONAN_ROOT +=  \\
$(CONAN_ROOT_MYPKG1) \\
$(CONAN_ROOT_MYPKG2)

CONAN_SYSROOT +=  \\
$(CONAN_SYSROOT_MYPKG1) \\
$(CONAN_SYSROOT_MYPKG2)

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
                                               conan_include_dirs_mypkg1=inc1,
                                               conan_lib_dirs_mypkg1=lib1,
                                               conan_bin_dirs_mypkg1=bin1,
                                               conan_build_dirs_mypkg1=root1,
                                               conan_root_mypkg2=root2,
                                               conan_include_dirs_mypkg2=inc2,
                                               conan_lib_dirs_mypkg2=lib2,
                                               conan_bin_dirs_mypkg2=bin2,
                                               conan_build_dirs_mypkg2=root2,
                                               conan_framework_dirs_mypkg1=root1)

    content = "\n".join(line.strip() for line in content.splitlines())  # Trailing spaces
    assert expected_content in content
