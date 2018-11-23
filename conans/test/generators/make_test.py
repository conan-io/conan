import unittest
from conans.model.conan_file import ConanFile
from conans.model.settings import Settings
from conans.model.env_info import EnvValues
from conans.model.ref import ConanFileReference
from conans.model.build_info import CppInfo
from conans.client.generators import MakeGenerator
from conans.test.utils.test_files import temp_folder
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
        generator = MakeGenerator(conanfile)
        content = generator.content

        self.assertIn("CONAN_DEFINES +=  \\\n$(CONAN_DEFINES_MYPKG1) \\\n$(CONAN_DEFINES_MYPKG2)",
                      content)
        self.assertIn("CONAN_DEFINES_MYPKG1 +=  \\\nMYDEFINE1", content)
        self.assertIn("CONAN_DEFINES_MYPKG2 +=  \\\nMYDEFINE2", content)

        inc1 = os.path.join(tmp_folder1, 'include1').replace('\\', '/')
        inc2 = os.path.join(tmp_folder2, 'include2').replace('\\', '/')
        self.assertIn("CONAN_INC_PATHS +=  \\\n"
                      "$(CONAN_INC_PATHS_MYPKG1) \\\n"
                      "$(CONAN_INC_PATHS_MYPKG2)", content)
        self.assertIn("CONAN_INC_PATHS_MYPKG1 +=  \\\n%s" % inc1, content)
        self.assertIn("CONAN_INC_PATHS_MYPKG2 +=  \\\n%s" % inc2, content)

        lib1 = os.path.join(tmp_folder1, 'lib1').replace('\\', '/')
        lib2 = os.path.join(tmp_folder2, 'lib2').replace('\\', '/')
        self.assertIn("CONAN_LIB_PATHS +=  \\\n"
                      "$(CONAN_LIB_PATHS_MYPKG1) \\\n"
                      "$(CONAN_LIB_PATHS_MYPKG2)", content)
        self.assertIn("CONAN_LIB_PATHS_MYPKG1 +=  \\\n%s" % lib1, content)
        self.assertIn("CONAN_LIB_PATHS_MYPKG2 +=  \\\n%s" % lib2, content)

        bin1 = os.path.join(tmp_folder1, 'bin1').replace('\\', '/')
        bin2 = os.path.join(tmp_folder2, 'bin2').replace('\\', '/')
        self.assertIn("CONAN_BIN_PATHS +=  \\\n"
                      "$(CONAN_BIN_PATHS_MYPKG1) \\\n"
                      "$(CONAN_BIN_PATHS_MYPKG2)", content)
        self.assertIn("CONAN_BIN_PATHS_MYPKG1 +=  \\\n%s" % bin1, content)
        self.assertIn("CONAN_BIN_PATHS_MYPKG2 +=  \\\n%s" % bin2, content)

        self.assertIn("CONAN_LIBS +=  \\\n$(CONAN_LIBS_MYPKG1) \\\n$(CONAN_LIBS_MYPKG2)", content)
        self.assertIn("CONAN_LIBS_MYPKG1 +=  \\\nlibfoo", content)
        self.assertIn("CONAN_LIBS_MYPKG2 +=  \\\nlibbar", content)

        self.assertIn("CONAN_CFLAGS +=  \\\n$(CONAN_CFLAGS_MYPKG1) \\\n$(CONAN_CFLAGS_MYPKG2)",
                      content)
        self.assertIn("CONAN_CFLAGS_MYPKG1 +=  \\\n-fPIC", content)
        self.assertIn("CONAN_CFLAGS_MYPKG2 +=  \\\n-mtune=native", content)

        self.assertIn("CONAN_CPPFLAGS +=  \\\n$(CONAN_CPPFLAGS_MYPKG1) \\\n$(CONAN_CPPFLAGS_MYPKG2)",
                      content)
        self.assertIn("CONAN_CPPFLAGS_MYPKG1 +=  \\\n-fPIE", content)
        self.assertIn("CONAN_CPPFLAGS_MYPKG2 +=  \\\n-march=native", content)

        self.assertIn("CONAN_SHAREDLINKFLAGS +=  \\\n"
                      "$(CONAN_SHAREDLINKFLAGS_MYPKG1) \\\n"
                      "$(CONAN_SHAREDLINKFLAGS_MYPKG2)", content)
        self.assertIn("CONAN_SHAREDLINKFLAGS_MYPKG1 +=  \\\n-framework Cocoa", content)
        self.assertIn("CONAN_SHAREDLINKFLAGS_MYPKG2 +=  \\\n-framework AudioFoundation", content)

        self.assertIn("CONAN_EXELINKFLAGS +=  \\\n"
                      "$(CONAN_EXELINKFLAGS_MYPKG1) \\\n"
                      "$(CONAN_EXELINKFLAGS_MYPKG2)", content)
        self.assertIn("CONAN_EXELINKFLAGS_MYPKG1 +=  \\\n-framework QuartzCore", content)
        self.assertIn("CONAN_EXELINKFLAGS_MYPKG2 +=  \\\n-framework VideoToolbox", content)
