import os
import shutil
import unittest
from collections import namedtuple

from conans.client.generators.cmake_paths import CMakePathsGenerator
from conans.model.build_info import CppInfo
from conans.model.conan_file import ConanFile
from conans.model.env_info import EnvValues
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient


class CMakePathsGeneratorTest(unittest.TestCase):

    def cmake_vars_unit_test(self):
        settings_mock = namedtuple("Settings", "build_type, os, os_build, constraint")
        settings = settings_mock("Release", None, None, lambda x: x)
        conanfile = ConanFile(None, None)
        conanfile.initialize(settings, EnvValues())
        tmp = temp_folder()
        cpp_info = CppInfo(tmp)
        custom_dir = os.path.join(tmp, "custom_build_dir")
        os.mkdir(custom_dir)
        cpp_info.builddirs.append(os.path.join(tmp, "custom_build_dir"))
        conanfile.deps_cpp_info.update(cpp_info, "MyLib")

        generator = CMakePathsGenerator(conanfile)
        cmake_lines = [s.replace("\t\t\t", "").replace('\\', '/')
                       for s in generator.content.splitlines()]
        self.assertEquals('set(CMAKE_MODULE_PATH '
                          '"%s/"' % tmp.replace('\\', '/'), cmake_lines[0])
        self.assertEquals('"%s" ${CMAKE_MODULE_PATH} '
                          '${CMAKE_CURRENT_LIST_DIR})' % custom_dir.replace('\\', '/'),
                          cmake_lines[1])
        self.assertEquals('set(CMAKE_PREFIX_PATH '
                          '"%s/"' % tmp.replace('\\', '/'), cmake_lines[2])
        self.assertEquals('"%s" ${CMAKE_PREFIX_PATH} '
                          '${CMAKE_CURRENT_LIST_DIR})' % custom_dir.replace('\\', '/'),
                          cmake_lines[3])
