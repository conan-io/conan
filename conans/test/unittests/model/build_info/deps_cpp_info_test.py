import unittest

import six

from conans.model.build_info import DepsCppInfo, CppInfo, DepCppInfo


class DepsCppInfoTestCase(unittest.TestCase):

    def test_types(self):
        deps_cpp_info = DepsCppInfo()
        cpp_info = CppInfo("pkg", "rootpath")
        cpp_info.version = "version"
        cpp_info.libs = ["lib1", "lib2"]
        cpp_info.includedirs = ["include1"]
        deps_cpp_info.add("pkg", DepCppInfo(cpp_info))

        info_for_package = deps_cpp_info["pkg"]

        # Documented as list for 'self.cpp_info' object
        self.assertIsInstance(info_for_package.includedirs, list)
        self.assertIsInstance(info_for_package.libdirs, list)
        self.assertIsInstance(info_for_package.resdirs, list)
        self.assertIsInstance(info_for_package.bindirs, list)
        self.assertIsInstance(info_for_package.builddirs, list)
        self.assertIsInstance(info_for_package.libs, list)
        self.assertIsInstance(info_for_package.defines, list)
        self.assertIsInstance(info_for_package.cflags, list)
        self.assertIsInstance(info_for_package.cppflags, list)
        self.assertIsInstance(info_for_package.cxxflags, list)
        self.assertIsInstance(info_for_package.sharedlinkflags, list)
        self.assertIsInstance(info_for_package.exelinkflags, list)
        self.assertIsInstance(info_for_package.frameworks, list)
        self.assertIsInstance(info_for_package.frameworkdirs, list)
        self.assertIsInstance(info_for_package.rootpath, six.string_types)
        self.assertIsInstance(info_for_package.name, six.string_types)
        self.assertIsInstance(info_for_package.system_libs, list)
        self.assertIsInstance(info_for_package.build_modules, dict)
        self.assertIsInstance(info_for_package.components, dict)

        # Documented as list for `deps_cpp_info["pkg"]`
        self.assertIsInstance(info_for_package.include_paths, list)
        self.assertIsInstance(info_for_package.lib_paths, list)
        self.assertIsInstance(info_for_package.bin_paths, list)
        self.assertIsInstance(info_for_package.build_paths, list)
        self.assertIsInstance(info_for_package.res_paths, list)
        self.assertIsInstance(info_for_package.framework_paths, list)
        self.assertIsInstance(info_for_package.build_modules_paths, dict)
        self.assertIsInstance(info_for_package.get_name("generator"), six.string_types)
        self.assertIsInstance(info_for_package.version, six.string_types)
        self.assertIsInstance(info_for_package.components, dict)
