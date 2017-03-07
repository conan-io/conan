import re
import unittest

from conans.client.generators import VisualStudioGenerator

from conans.model.settings import Settings
from conans.model.conan_file import ConanFile
from conans.client.generators.cmake import CMakeGenerator
from conans.model.build_info import CppInfo
from conans.model.ref import ConanFileReference


class VisualStudioGeneratorTest(unittest.TestCase):

    def variables_setup_test(self):
        conanfile = ConanFile(None, None, Settings({}), None)
        ref = ConanFileReference.loads("MyPkg/0.1@lasote/stables")
        cpp_info = CppInfo("dummy_root_folder1")
        cpp_info.defines = ["MYDEFINE1"]
        conanfile.deps_cpp_info.update(cpp_info, ref)
        ref = ConanFileReference.loads("MyPkg2/0.1@lasote/stables")
        cpp_info = CppInfo("dummy_root_folder2")
        cpp_info.defines = ["MYDEFINE2"]
        conanfile.deps_cpp_info.update(cpp_info, ref)
        generator = VisualStudioGenerator(conanfile)
        content = generator.content
        lines = content.splitlines()
        self.assertIn('<PropertyGroup Label="MyPkg">', content)
        self.assertIn("<Conan.MyPkg.Root>dummy_root_folder1</Conan.MyPkg.Root>", content)
        self.assertIn("<Conan.Defines.MyPkg>MYDEFINE1</Conan.Defines.MyPkg>", content)
        self.assertIn("<Conan.Defines.MyPkg2>MYDEFINE2</Conan.Defines.MyPkg2>", content)

    def multi_flag_test(self):
        conanfile = ConanFile(None, None, Settings({}), None)
        ref = ConanFileReference.loads("MyPkg/0.1@lasote/stables")
        cpp_info = CppInfo("dummy_root_folder1")
        cpp_info.includedirs.append("other_include_dir")
        cpp_info.cppflags = ["-DGTEST_USE_OWN_TR1_TUPLE=1", "-DGTEST_LINKED_AS_SHARED_LIBRARY=1"]
        conanfile.deps_cpp_info.update(cpp_info, ref)
        ref = ConanFileReference.loads("MyPkg2/0.1@lasote/stables")
        cpp_info = CppInfo("dummy_root_folder2")
        cpp_info.cflags = ["-DSOMEFLAG=1"]
        conanfile.deps_cpp_info.update(cpp_info, ref)
        generator = VisualStudioGenerator(conanfile)
        content = generator.content
        self.assertIn("<Conan.CompilerFlags.MyPkg>-DGTEST_USE_OWN_TR1_TUPLE=1 -DGTEST_LINKED_AS_SHARED_LIBRARY=1",
                      content)
        self.assertIn("<AdditionalOptions>-DGTEST_USE_OWN_TR1_TUPLE=1 -DGTEST_LINKED_AS_SHARED_LIBRARY=1"
                      " -DSOMEFLAG=1 %(AdditionalOptions)</AdditionalOptions>", content)
