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
        self.assertIsInstance(info_for_package.includedirs, (tuple, list))
        self.assertIsInstance(info_for_package.libdirs, (tuple, list))
        self.assertIsInstance(info_for_package.resdirs, (tuple, list))
        self.assertIsInstance(info_for_package.bindirs, (tuple, list))
        self.assertIsInstance(info_for_package.builddirs, (tuple, list))
        self.assertIsInstance(info_for_package.libs, (tuple, list))
        self.assertIsInstance(info_for_package.defines, (tuple, list))
        self.assertIsInstance(info_for_package.cflags, (tuple, list))
        self.assertIsInstance(info_for_package.cppflags, (tuple, list))
        self.assertIsInstance(info_for_package.cxxflags, (tuple, list))
        self.assertIsInstance(info_for_package.sharedlinkflags, (tuple, list))
        self.assertIsInstance(info_for_package.exelinkflags, (tuple, list))
        self.assertIsInstance(info_for_package.frameworks, (tuple, list))
        self.assertIsInstance(info_for_package.frameworkdirs, (tuple, list))
        self.assertIsInstance(info_for_package.rootpath, six.string_types)
        self.assertIsInstance(info_for_package.name, six.string_types)
        self.assertIsInstance(info_for_package.system_libs, (tuple, list))
        self.assertIsInstance(info_for_package.build_modules, (tuple, list))
        self.assertIsInstance(info_for_package.components, dict)

        # Documented as list for `deps_cpp_info["pkg"]`
        self.assertIsInstance(info_for_package.include_paths, (tuple, list))
        self.assertIsInstance(info_for_package.lib_paths, (tuple, list))
        self.assertIsInstance(info_for_package.bin_paths, (tuple, list))
        self.assertIsInstance(info_for_package.build_paths, (tuple, list))
        self.assertIsInstance(info_for_package.res_paths, (tuple, list))
        self.assertIsInstance(info_for_package.framework_paths, (tuple, list))
        self.assertIsInstance(info_for_package.build_modules_paths, (tuple, list))
        self.assertIsInstance(info_for_package.get_name("generator"), six.string_types)
        self.assertIsInstance(info_for_package.version, six.string_types)
        self.assertIsInstance(info_for_package.components, dict)
