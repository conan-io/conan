import unittest
from conans.model.settings import Settings
from conans.model.conan_file import ConanFile
from conans.client.generators.scons import SConsGenerator
from conans.model.build_info import CppInfo
from conans.model.ref import ConanFileReference


class SConsGeneratorTest(unittest.TestCase):
    def variables_setup_test(self):
        conanfile = ConanFile(None, None, Settings({}), None)
        ref = ConanFileReference.loads("MyPkg/0.1@lasote/stables")
        cpp_info = CppInfo("")
        cpp_info.defines = ["MYDEFINE1"]
        cpp_info.version = "0.1"
        conanfile.deps_cpp_info.update(cpp_info, ref.name)
        ref = ConanFileReference.loads("MyPkg2/3.2.3@lasote/stables")
        cpp_info = CppInfo("")
        cpp_info.defines = ["MYDEFINE2"]
        cpp_info.version = "3.2.3"
        conanfile.deps_cpp_info.update(cpp_info, ref.name)
        generator = SConsGenerator(conanfile)
        content = generator.content
        scons_lines = content.splitlines()
        self.assertIn("        \"CPPDEFINES\"  : [\'MYDEFINE2\', \'MYDEFINE1\'],", scons_lines)
        self.assertIn("        \"CPPDEFINES\"  : [\'MYDEFINE1\'],", scons_lines)
        self.assertIn("        \"CPPDEFINES\"  : [\'MYDEFINE2\'],", scons_lines)
        self.assertIn("        \"VERSION\"     : \"None\",", scons_lines)
        self.assertIn("        \"VERSION\"     : \"0.1\",", scons_lines)
        self.assertIn("        \"VERSION\"     : \"3.2.3\",", scons_lines)
