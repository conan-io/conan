import os
import unittest
from collections import defaultdict, namedtuple

import pytest

from conans.test.utils.test_files import temp_folder
from conans.util.files import mkdir


@pytest.mark.xfail(reason="DepsCppInfo removed")
class BuildInfoTest(unittest.TestCase):
    def test_BuildModulesDict(self):
        build_modules = BuildModulesDict({"cmake": ["whatever.cmake"]})
        build_modules.extend(["hello.cmake"])
        assert build_modules["cmake"] == ["whatever.cmake", "hello.cmake"]
        build_modules = dict_to_abs_paths(build_modules, "root")
        assert build_modules["cmake"] == [os.path.join("root", "whatever.cmake"),
                                          os.path.join("root", "hello.cmake")]
        build_modules = BuildModulesDict.from_list(["this.cmake", "this_not.pc"])
        assert build_modules == {"cmake": ["this.cmake"],
                                 "cmake_multi": ["this.cmake"],
                                 "cmake_find_package": ["this.cmake"],
                                 "cmake_find_package_multi": ["this.cmake"]}

    def test_cpp_info(self):
        folder = temp_folder()
        mkdir(os.path.join(folder, "include"))
        mkdir(os.path.join(folder, "lib"))
        mkdir(os.path.join(folder, "local_bindir"))
        abs_folder = temp_folder()
        abs_include = os.path.join(abs_folder, "usr/include")
        abs_lib = os.path.join(abs_folder, "usr/lib")
        abs_bin = os.path.join(abs_folder, "usr/bin")
        mkdir(abs_include)
        mkdir(abs_lib)
        mkdir(abs_bin)
        info = CppInfo("", folder)
        info.includedirs.append(abs_include)
        info.libdirs.append(abs_lib)
        info.bindirs.append(abs_bin)
        info.bindirs.append("local_bindir")
        self.assertListEqual(list(info.include_paths), [os.path.join(folder, "include"), abs_include])
        self.assertListEqual(list(info.lib_paths), [os.path.join(folder, "lib"), abs_lib])
        self.assertListEqual(list(info.bin_paths), [abs_bin, os.path.join(folder, "local_bindir")])

    def test_cpp_info_system_libs(self):
        info1 = CppInfo("dep1", "folder1")
        info1.system_libs = ["sysdep1"]
        info2 = CppInfo("dep2", "folder2")
        info2.system_libs = ["sysdep2", "sysdep3"]
        deps_cpp_info = DepsCppInfo()
        deps_cpp_info.add("dep1", DepCppInfo(info1))
        deps_cpp_info.add("dep2", DepCppInfo(info2))
        self.assertListEqual(["sysdep1", "sysdep2", "sysdep3"], list(deps_cpp_info.system_libs))
        self.assertListEqual(["sysdep1"], list(deps_cpp_info["dep1"].system_libs))
        self.assertListEqual(["sysdep2", "sysdep3"], list(deps_cpp_info["dep2"].system_libs))

    def test_cpp_info_name(self):
        folder = temp_folder()
        info = CppInfo("myname", folder)
        info.name = "MyName"
        info.names["my_generator"] = "MyNameForMyGenerator"
        deps_cpp_info = DepsCppInfo()
        deps_cpp_info.add("myname", DepCppInfo(info))
        self.assertIn("MyName", deps_cpp_info["myname"].get_name("my_undefined_generator"))
        self.assertIn("MyNameForMyGenerator", deps_cpp_info["myname"].get_name("my_generator"))

    def test_cpp_info_build_modules(self):
        folder = temp_folder()
        info = CppInfo("myname", folder)
        info.build_modules.append("old.cmake")  # Test old behavior with .cmake build modules
        info.build_modules.extend(["other_old.cmake", "file.pc"])  # .pc not considered
        info.build_modules["generator"].append("my_module.cmake")
        info.debug.build_modules["other_gen"] = ["mod-release.cmake"]
        deps_cpp_info = DepsCppInfo()
        deps_cpp_info.add("myname", DepCppInfo(info))
        for gen in ["cmake", "cmake_multi", "cmake_find_package", "cmake_find_package_multi"]:
            self.assertListEqual([os.path.join(folder, "old.cmake"),
                                  os.path.join(folder, "other_old.cmake")],
                                 list(deps_cpp_info["myname"].build_modules_paths[gen]))
        self.assertListEqual([os.path.join(folder, "my_module.cmake")],
                             list(deps_cpp_info["myname"].build_modules_paths["generator"]))
        self.assertListEqual([os.path.join(folder, "mod-release.cmake")],
                             list(deps_cpp_info["myname"].debug.build_modules_paths["other_gen"]))

    def test_cpp_info_build_modules_old_behavior(self):
        folder = temp_folder()
        info = CppInfo("myname", folder)
        info.build_modules = ["old.cmake"]  # Test old behavior with .cmake build modules as list
        deps_cpp_info = DepsCppInfo()
        deps_cpp_info.add("myname", DepCppInfo(info))
        for gen in ["cmake", "cmake_multi", "cmake_find_package", "cmake_find_package_multi"]:
            assert list(deps_cpp_info["myname"].build_modules_paths[gen]) ==\
                   [os.path.join(folder, "old.cmake")]

    def test_cppinfo_public_interface(self):
        folder = temp_folder()
        info = CppInfo("", folder)
        self.assertEqual([], info.libs)
        self.assertEqual([], info.system_libs)
        self.assertEqual(["include"], info.includedirs)
        self.assertEqual([], info.srcdirs)
        self.assertEqual(["res"], info.resdirs)
        self.assertEqual([""], info.builddirs)
        self.assertEqual(["bin"], info.bindirs)
        self.assertEqual(["lib"], info.libdirs)
        self.assertEqual(folder, info.rootpath)
        self.assertEqual([], info.defines)
        self.assertEqual("", info.sysroot)
        self.assertEqual([], info.cflags)
        self.assertEqual({}, info.configs)
        self.assertEqual([], info.cxxflags)
        self.assertEqual([], info.exelinkflags)
        self.assertEqual([], info.sharedlinkflags)
