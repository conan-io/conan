import os
import textwrap
import unittest

from mock import Mock

from conans.client.generators import PremakeGenerator
from conans.model.build_info import CppInfo
from conans.model.conan_file import ConanFile
from conans.model.env_info import EnvValues
from conans.model.ref import ConanFileReference
from conans.model.settings import Settings
from conans.test.utils.test_files import temp_folder
from conans.util.files import save


class PremakeGeneratorTest(unittest.TestCase):
    content_template = textwrap.dedent("""\
    #!lua
    conan_build_type = "None"
    conan_arch = "None"

    conan_includedirs = {{"{include1}",
    "{include2}"}}
    conan_libdirs = {{"{lib1}",
    "{lib2}"}}
    conan_bindirs = {{"{bin1}",
    "{bin2}"}}
    conan_libs = {{"libfoo", "libbar"}}
    conan_system_libs = {{"syslib1", "syslib2"}}
    conan_defines = {{"MYDEFINE2", "MYDEFINE1"}}
    conan_cxxflags = {{"-march=native", "-fPIE"}}
    conan_cflags = {{"-mtune=native", "-fPIC"}}
    conan_sharedlinkflags = {{"-framework AudioFoundation", "-framework \\\"Some Spaced Framework\\\"", "-framework Cocoa"}}
    conan_exelinkflags = {{"-framework VideoToolbox", "-framework \\\"Other Spaced Framework\\\"", "-framework QuartzCore"}}
    conan_frameworks = {{"AudioUnit.framework"}}

    conan_includedirs_MyPkg1 = {{"{include1}"}}
    conan_libdirs_MyPkg1 = {{"{lib1}"}}
    conan_bindirs_MyPkg1 = {{"{bin1}"}}
    conan_libs_MyPkg1 = {{"libfoo"}}
    conan_system_libs_MyPkg1 = {{"syslib1"}}
    conan_defines_MyPkg1 = {{"MYDEFINE1"}}
    conan_cxxflags_MyPkg1 = {{"-fPIE"}}
    conan_cflags_MyPkg1 = {{"-fPIC"}}
    conan_sharedlinkflags_MyPkg1 = {{"-framework Cocoa"}}
    conan_exelinkflags_MyPkg1 = {{"-framework QuartzCore"}}
    conan_frameworks_MyPkg1 = {{"AudioUnit.framework"}}
    conan_rootpath_MyPkg1 = "{root1}"

    conan_includedirs_MyPkg2 = {{"{include2}"}}
    conan_libdirs_MyPkg2 = {{"{lib2}"}}
    conan_bindirs_MyPkg2 = {{"{bin2}"}}
    conan_libs_MyPkg2 = {{"libbar"}}
    conan_system_libs_MyPkg2 = {{"syslib2"}}
    conan_defines_MyPkg2 = {{"MYDEFINE2"}}
    conan_cxxflags_MyPkg2 = {{"-march=native"}}
    conan_cflags_MyPkg2 = {{"-mtune=native"}}
    conan_sharedlinkflags_MyPkg2 = {{"-framework AudioFoundation", "-framework \\\"Some Spaced Framework\\\""}}
    conan_exelinkflags_MyPkg2 = {{"-framework VideoToolbox", "-framework \\\"Other Spaced Framework\\\""}}
    conan_frameworks_MyPkg2 = {{}}
    conan_rootpath_MyPkg2 = "{root2}"

    function conan_basic_setup()
        configurations{{conan_build_type}}
        architecture(conan_arch)
        includedirs{{conan_includedirs}}
        libdirs{{conan_libdirs}}
        links{{conan_libs}}
        links{{conan_system_libs}}
        links{{conan_frameworks}}
        defines{{conan_defines}}
        bindirs{{conan_bindirs}}
    end
    """)

    def setUp(self):
        self.tmp_folder1 = temp_folder()
        self.tmp_folder2 = temp_folder()
        save(os.path.join(self.tmp_folder1, "include1", "file.h"), "")
        save(os.path.join(self.tmp_folder2, "include2", "file.h"), "")
        save(os.path.join(self.tmp_folder1, "lib1", "file.a"), "")
        save(os.path.join(self.tmp_folder2, "lib2", "file.a"), "")
        save(os.path.join(self.tmp_folder1, "bin1", "file.bin"), "")
        save(os.path.join(self.tmp_folder2, "bin2", "file.bin"), "")

        self.conanfile = ConanFile(Mock(), None)
        self.conanfile.initialize(Settings({}), EnvValues())
        ref = ConanFileReference.loads("MyPkg1/0.1@lasote/stables")
        cpp_info = CppInfo(ref.name, self.tmp_folder1)
        cpp_info.defines = ["MYDEFINE1"]
        cpp_info.includedirs = ['include1']
        cpp_info.libdirs = ['lib1']
        cpp_info.libs = ['libfoo']
        cpp_info.system_libs = ['syslib1']
        cpp_info.bindirs = ['bin1']
        cpp_info.version = "0.1"
        cpp_info.cflags = ['-fPIC']
        cpp_info.cxxflags = ['-fPIE']
        cpp_info.sharedlinkflags = ['-framework Cocoa']
        cpp_info.exelinkflags = ['-framework QuartzCore']
        cpp_info.frameworks = ['AudioUnit']
        self.conanfile.deps_cpp_info.add(ref.name, cpp_info)
        ref = ConanFileReference.loads("MyPkg2/3.2.3@lasote/stables")
        cpp_info = CppInfo(ref.name, self.tmp_folder2)
        cpp_info.defines = ["MYDEFINE2"]
        cpp_info.includedirs = ['include2']
        cpp_info.libdirs = ['lib2']
        cpp_info.libs = ['libbar']
        cpp_info.system_libs = ['syslib2']
        cpp_info.bindirs = ['bin2']
        cpp_info.version = "3.2.3"
        cpp_info.cflags = ['-mtune=native']
        cpp_info.cxxflags = ['-march=native']
        cpp_info.sharedlinkflags = ['-framework AudioFoundation', '-framework "Some Spaced Framework"']
        cpp_info.exelinkflags = ['-framework VideoToolbox', '-framework "Other Spaced Framework"']
        self.conanfile.deps_cpp_info.add(ref.name, cpp_info)

    def test_variables_content(self):
        generator = PremakeGenerator(self.conanfile)
        content = generator.content

        inc1 = os.path.join(self.tmp_folder1, 'include1').replace('\\', '/')
        inc2 = os.path.join(self.tmp_folder2, 'include2').replace('\\', '/')

        lib1 = os.path.join(self.tmp_folder1, 'lib1').replace('\\', '/')
        lib2 = os.path.join(self.tmp_folder2, 'lib2').replace('\\', '/')

        bin1 = os.path.join(self.tmp_folder1, 'bin1').replace('\\', '/')
        bin2 = os.path.join(self.tmp_folder2, 'bin2').replace('\\', '/')

        root1 = self.tmp_folder1.replace('\\', '/')
        root2 = self.tmp_folder2.replace('\\', '/')

        expected_content = self.content_template.format(include1=inc1, include2=inc2,
                                                        lib1=lib1, lib2=lib2,
                                                        bin1=bin1, bin2=bin2,
                                                        root1=root1, root2=root2)
        self.assertEqual(expected_content, content)
