import re
import unittest

from conans.client.generators.qmake_subdirs import QmakeSubDirsGenerator
from conans.model.settings import Settings
from conans.model.conan_file import ConanFile
from conans.client.generators.cmake import CMakeGenerator
from conans.model.build_info import CppInfo
from conans.model.ref import ConanFileReference
from conans.client.conf import default_settings_yml
from conans.test.utils.test_files import temp_folder
from conans.util.files import save
import os
from conans.model.env_info import EnvValues


class QMakeSubDirsGeneratorTest(unittest.TestCase):


    def test_variables_setup(self):
        conanfile = ConanFile(None, None)
        conanfile.initialize(Settings({}), EnvValues())
        ref = ConanFileReference.loads("MyPkg/0.1@lasote/stables")
        cpp_info = CppInfo("dummy_root_folder1")
        cpp_info.defines = ["MYDEFINE1"]
        conanfile.deps_cpp_info.update(cpp_info, ref.name)
        ref = ConanFileReference.loads("MyPkg2/0.1@lasote/stables")
        cpp_info = CppInfo("dummy_root_folder2")
        cpp_info.defines = ["MYDEFINE2"]
        conanfile.deps_cpp_info.update(cpp_info, ref.name)
        conanfile.deps_user_info["LIB1"].myvar = "myvalue"
        conanfile.deps_user_info["LIB1"].myvar2 = "myvalue2"
        conanfile.deps_user_info["lib2"].MYVAR2 = "myvalue4"
        generator = QmakeSubDirsGenerator(conanfile)
        self.assertEquals( generator.filename, "conan_subdirs.pri")

        content = generator.content
        cmake_lines = content.splitlines()
        self.assertIn('#todo', cmake_lines)
