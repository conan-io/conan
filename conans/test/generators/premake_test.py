import unittest
from conans.model.conan_file import ConanFile
from conans.model.settings import Settings
from conans.model.env_info import EnvValues
from conans.model.ref import ConanFileReference
from conans.model.build_info import CppInfo
from conans.client.generators import PremakeGenerator
from conans.test.utils.test_files import temp_folder
from conans.util.files import save
import os


class PremakeGeneratorTest(unittest.TestCase):
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
        cpp_info.cflags = ['-fPIC']
        cpp_info.cppflags = ['-fPIE']
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
        cpp_info.cflags = ['-mtune=native']
        cpp_info.cppflags = ['-march=native']
        cpp_info.sharedlinkflags = ['-framework AudioFoundation']
        cpp_info.exelinkflags = ['-framework VideoToolbox']
        conanfile.deps_cpp_info.update(cpp_info, ref.name)
        generator = PremakeGenerator(conanfile)
        content = generator.content

        self.assertIn('conan_cppdefines = {"MYDEFINE2", "MYDEFINE1"}', content)
        self.assertIn('conan_cppdefines_MyPkg1 = {"MYDEFINE1"}', content)
        self.assertIn('conan_cppdefines_MyPkg2 = {"MYDEFINE2"}', content)

        inc1 = os.path.join(tmp_folder1, 'include1').replace('\\', '/')
        inc2 = os.path.join(tmp_folder2, 'include2').replace('\\', '/')
        self.assertIn('conan_includedirs = {"%s",\n"%s"}' % (inc1, inc2), content)
        self.assertIn('conan_includedirs_MyPkg1 = {"%s"}' % inc1, content)
        self.assertIn('conan_includedirs_MyPkg2 = {"%s"}' % inc2, content)

        lib1 = os.path.join(tmp_folder1, 'lib1').replace('\\', '/')
        lib2 = os.path.join(tmp_folder2, 'lib2').replace('\\', '/')
        self.assertIn('conan_libdirs = {"%s",\n"%s"}' % (lib1, lib2), content)
        self.assertIn('conan_libdirs_MyPkg1 = {"%s"}' % lib1, content)
        self.assertIn('conan_libdirs_MyPkg2 = {"%s"}' % lib2, content)

        bin1 = os.path.join(tmp_folder1, 'bin1').replace('\\', '/')
        bin2 = os.path.join(tmp_folder2, 'bin2').replace('\\', '/')
        self.assertIn('conan_bindirs = {"%s",\n"%s"}' % (bin1, bin2), content)
        self.assertIn('conan_bindirs_MyPkg1 = {"%s"}' % bin1, content)
        self.assertIn('conan_bindirs_MyPkg2 = {"%s"}' % bin2, content)

        self.assertIn('conan_libs = {"libfoo", "libbar"}', content)
        self.assertIn('conan_libs_MyPkg1 = {"libfoo"}', content)
        self.assertIn('conan_libs_MyPkg2 = {"libbar"}', content)

        self.assertIn('conan_cflags = {"-mtune=native", "-fPIC"}', content)
        self.assertIn('conan_cflags_MyPkg1 = {"-fPIC"}', content)
        self.assertIn('conan_cflags_MyPkg2 = {"-mtune=native"}', content)

        self.assertIn('conan_cppflags = {"-march=native", "-fPIE"}', content)
        self.assertIn('conan_cppflags_MyPkg1 = {"-fPIE"}', content)
        self.assertIn('conan_cppflags_MyPkg2 = {"-march=native"}', content)

        self.assertIn('conan_sharedlinkflags = {"-framework AudioFoundation", "-framework Cocoa"}', content)
        self.assertIn('conan_sharedlinkflags_MyPkg1 = {"-framework Cocoa"}', content)
        self.assertIn('conan_sharedlinkflags_MyPkg2 = {"-framework AudioFoundation"}', content)

        self.assertIn('conan_exelinkflags = {"-framework VideoToolbox", "-framework QuartzCore"}', content)
        self.assertIn('conan_exelinkflags_MyPkg1 = {"-framework QuartzCore"}', content)
        self.assertIn('conan_exelinkflags_MyPkg2 = {"-framework VideoToolbox"}', content)
