import os
import unittest

from mock import Mock

from conans.client.generators.cmake_paths import CMakePathsGenerator
from conans.model.build_info import CppInfo
from conans.model.conan_file import ConanFile
from conans.model.env_info import EnvValues
from conans.test.utils.test_files import temp_folder
from conans.errors import ConanException


class _MockSettings(object):
    build_type = None
    os = None
    os_build = None
    fields = []

    def __init__(self, build_type=None):
        self.build_type = build_type

    @property
    def compiler(self):
        raise ConanException("mock: not available")

    def constraint(self, _):
        return self

    def get_safe(self, _):
        return None

    def items(self):
        return {}


class CMakePathsGeneratorTest(unittest.TestCase):

    def test_cmake_vars_unit(self):
        settings = _MockSettings("Release")
        conanfile = ConanFile(Mock(), None)
        conanfile.initialize(settings, EnvValues())
        tmp = temp_folder()
        cpp_info = CppInfo("MyLib", tmp)
        custom_dir = os.path.join(tmp, "custom_build_dir")
        os.mkdir(custom_dir)
        cpp_info.builddirs.append(os.path.join(tmp, "custom_build_dir"))
        conanfile.deps_cpp_info.add("MyLib", cpp_info)

        generator = CMakePathsGenerator(conanfile)
        path = tmp.replace('\\', '/')
        custom_dir = custom_dir.replace('\\', '/')
        cmake_lines = generator.content.replace('\\', '/').replace("\n\t\t\t", " ").splitlines()
        self.assertEqual('set(CONAN_MYLIB_ROOT "%s")' % path, cmake_lines[0])
        self.assertEqual('set(CMAKE_MODULE_PATH "%s/" "%s" ${CONAN_MYLIB_ROOT} ${CMAKE_MODULE_PATH} '
                         '${CMAKE_CURRENT_LIST_DIR})' % (path, custom_dir), cmake_lines[1])
        self.assertEqual('set(CMAKE_PREFIX_PATH "%s/" "%s" ${CONAN_MYLIB_ROOT} ${CMAKE_PREFIX_PATH} '
                         '${CMAKE_CURRENT_LIST_DIR})' % (path, custom_dir), cmake_lines[2])

    def test_cpp_info_name(self):
        settings = _MockSettings("Release")
        conanfile = ConanFile(Mock(), None)
        conanfile.initialize(settings, EnvValues())
        tmp = temp_folder()
        cpp_info = CppInfo("pkg_reference_name", tmp)
        cpp_info.name = "PkgCMakeName"
        conanfile.deps_cpp_info.add("pkg_reference_name", cpp_info)
        generator = CMakePathsGenerator(conanfile)
        self.assertIn('set(CONAN_PKGCMAKENAME_ROOT', generator.content)

    def test_cpp_info_names(self):
        settings = _MockSettings("Release")
        conanfile = ConanFile(Mock(), None)
        conanfile.initialize(settings, EnvValues())
        tmp = temp_folder()
        cpp_info = CppInfo("pkg_reference_name", tmp)
        cpp_info.name = "PkgCMakeName"
        cpp_info.names["cmake_paths"] = "MyCMakePathsPkgName"
        conanfile.deps_cpp_info.add("pkg_reference_name", cpp_info)
        generator = CMakePathsGenerator(conanfile)
        self.assertIn('set(CONAN_MYCMAKEPATHSPKGNAME_ROOT', generator.content)
