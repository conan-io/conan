import platform
import unittest

from conans.client.generators.scons import SConsGenerator
from conans.model.build_info import CppInfo, DepCppInfo
from conans.model.conan_file import ConanFile
from conans.model.env_info import EnvValues
from conans.model.ref import ConanFileReference
from conans.model.settings import Settings
from conans.test.utils.tools import TestBufferConanOutput


class SConsGeneratorTest(unittest.TestCase):

    def variables_setup_test(self):
        conanfile = ConanFile(TestBufferConanOutput(), None)
        conanfile.initialize(Settings({}), EnvValues())
        ref = ConanFileReference.loads("MyPkg/0.1@lasote/stables")
        cpp_info = CppInfo(ref.name, "")
        cpp_info.defines = ["MYDEFINE1"]
        cpp_info.version = "0.1"
        conanfile.deps_cpp_info.add(ref.name, cpp_info)
        ref = ConanFileReference.loads("MyPkg2/3.2.3@lasote/stables")
        cpp_info = CppInfo(ref.name, "")
        cpp_info.defines = ["MYDEFINE2"]
        cpp_info.version = "3.2.3"
        conanfile.deps_cpp_info.add(ref.name, DepCppInfo(cpp_info))
        generator = SConsGenerator(conanfile)
        content = generator.content
        scons_lines = content.splitlines()
        self.assertIn("        \"CPPDEFINES\"  : ['MYDEFINE2', 'MYDEFINE1'],", scons_lines)
        self.assertIn("        \"CPPDEFINES\"  : ['MYDEFINE1'],", scons_lines)
        self.assertIn("        \"CPPDEFINES\"  : ['MYDEFINE2'],", scons_lines)
        self.assertIn('    "conan_version" : "None",', scons_lines)
        self.assertIn('    "MyPkg_version" : "0.1",', scons_lines)
        self.assertIn('    "MyPkg2_version" : "3.2.3",', scons_lines)

    def system_frameworks_libs_test(self):
        # https://github.com/conan-io/conan/issues/7301
        conanfile = ConanFile(TestBufferConanOutput(), None)
        conanfile.initialize(Settings({}), EnvValues())
        cpp_info = CppInfo("MyPkg", "/rootpath")
        cpp_info.version = "0.1"
        cpp_info.libs = ["mypkg"]
        cpp_info.system_libs = ["pthread"]
        cpp_info.frameworks = ["cocoa"]
        cpp_info.frameworkdirs = ["frameworks"]
        cpp_info.filter_empty = False
        conanfile.deps_cpp_info.add("MyPkg", DepCppInfo(cpp_info))
        generator = SConsGenerator(conanfile)
        content = generator.content
        scons_lines = content.splitlines()
        self.assertIn('        "LIBS"        : [\'mypkg\', \'pthread\'],', scons_lines)
        self.assertIn('        "FRAMEWORKS"  : [\'cocoa\'],', scons_lines)
        if platform.system() == "Windows":
            self.assertIn('        "FRAMEWORKPATH"  : [\'/rootpath\\\\frameworks\'],', scons_lines)
        else:
            self.assertIn('        "FRAMEWORKPATH"  : [\'/rootpath/frameworks\'],', scons_lines)
        self.assertIn('    "MyPkg_version" : "0.1",', scons_lines)
