import re
import unittest

from conans.client.generators.qmake_subdirs import QmakeSubDirsGenerator
from conans.paths import BUILD_INFO_QMAKE_SUBDIRS
from conans.model.settings import Settings
from conans.model.conan_file import ConanFile
from conans.model.build_info import CppInfo
from conans.model.ref import ConanFileReference
from conans.model.env_info import EnvValues
from conans.test.utils.tools import TestBufferConanOutput



class QMakeSubDirsGeneratorTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.conanfile = ConanFile(TestBufferConanOutput(), None)
        cls.conanfile.initialize(Settings({}), EnvValues())
        ref = ConanFileReference.loads("MyPkg/0.1@lasote/stables")
        cpp_info = CppInfo("dummy_root_folder1")
        cpp_info.defines = ["MYDEFINE1"]
        cls.conanfile.deps_cpp_info.update(cpp_info, ref.name)
        ref = ConanFileReference.loads("MyPkg2/0.1@lasote/stables")
        cpp_info = CppInfo("dummy_root_folder2")
        cpp_info.defines = ["MYDEFINE2"]
        cls.conanfile.deps_cpp_info.update(cpp_info, ref.name)
        cls.conanfile.deps_user_info["LIB1"].myvar = "myvalue"
        cls.conanfile.deps_user_info["LIB1"].myvar2 = "myvalue2"
        cls.conanfile.deps_user_info["lib2"].MYVAR2 = "myvalue4"
        cls.generator = QmakeSubDirsGenerator(cls.conanfile)
        cls.content = cls.generator.content

    def test_qmake_subdirs_generates_multiple_files_test(self):

        self.assertIsNone(self.generator.filename)
        self.assertIsInstance(self.content,dict)
        self.assertTrue( len(self.content) is 3)

    def test_qmake_subdirs_generate_buildinfo_file_test(self):
        self.assertTrue( BUILD_INFO_QMAKE_SUBDIRS in self.content)

    def test_qmake_subdirs_generate_one_prf_file_per_dependancy_test(self):
        self.assertTrue("MyPkg.prf" in self.content)
        self.assertTrue("MyPkg2.prf" in self.content)

    def test_qmake_subdirs_declare_defines_in_prf_files(self):
        prf_lines = self.content["MyPkg.prf"].splitlines()
        self.assertIn('DEFINES *= "MYDEFINE1"', prf_lines)

        prf_lines = self.content["MyPkg2.prf"].splitlines()
        self.assertIn('DEFINES *= "MYDEFINE2"', prf_lines)

