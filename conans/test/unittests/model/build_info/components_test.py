# coding=utf-8
import os
import unittest
import warnings

from conans.model.build_info import CppInfo, DepsCppInfo, DepCppInfo
from conans.test.utils.test_files import temp_folder


class CppInfoComponentsTest(unittest.TestCase):

    def test_components_set(self):
        cpp_info = CppInfo("root_folder")
        cpp_info.components["liba"].name = "LIBA"
        cpp_info.components["libb"].includedirs.append("includewhat")
        cpp_info.components["libc"].libs.append("thelibc")
        self.assertListEqual(list(cpp_info.components.keys()), ["liba", "libb", "libc"])
        self.assertEqual(cpp_info.components["liba"].name, "LIBA")
        self.assertListEqual(cpp_info.components["libb"].includedirs, ["include", "includewhat"])
        self.assertListEqual(cpp_info.components["libc"].libs, ["thelibc"])

    def test_no_components_inside_components(self):
        cpp_info = CppInfo("root_folder")
        cpp_info.components["liba"].name = "LIBA"
        with self.assertRaises(AttributeError):
            cpp_info.components["libb"].components

    def test_deps_cpp_info_libs(self):
        deps_cpp_info = DepsCppInfo()

        dep1 = CppInfo("root")
        dep1.components["liba"].libs.append("liba")
        dep1.components["libb"].libs.append("libb")
        deps_cpp_info.update(DepCppInfo(dep1), "dep1")

        dep2 = CppInfo("root")
        dep2.components["libc"].libs.append("libc")
        dep2.components["libd"].libs.append("libd")
        deps_cpp_info.update(DepCppInfo(dep2), "dep2")

        dep3 = CppInfo("root")
        dep3.libs.append("libdep3")
        deps_cpp_info.update(DepCppInfo(dep3), "dep3")

        self.assertListEqual(["liba", "libb"], deps_cpp_info["dep1"].libs)
        self.assertListEqual(["libc", "libd"], deps_cpp_info["dep2"].libs)
        self.assertListEqual(["libdep3"], deps_cpp_info["dep3"].libs)
        self.assertListEqual(["liba", "libb", "libc", "libd", "libdep3"],
                             deps_cpp_info.libs)

    def test_deps_cpp_info_paths(self):
        deps_cpp_info = DepsCppInfo()

        folder1 = temp_folder()
        dep1 = CppInfo(folder1)
        os.mkdir(os.path.join(folder1, "include"))
        os.mkdir(os.path.join(folder1, "includea"))
        os.mkdir(os.path.join(folder1, "includeb"))
        dep1.components["liba"].includedirs.append("includea")
        dep1.components["libb"].includedirs.append("includeb")
        deps_cpp_info.update(DepCppInfo(dep1), "dep1")

        folder2 = temp_folder()
        dep2 = CppInfo(folder2)
        os.mkdir(os.path.join(folder2, "include"))
        os.mkdir(os.path.join(folder2, "includec"))
        os.mkdir(os.path.join(folder2, "included"))
        dep2.components["libc"].includedirs.append("includec")
        dep2.components["libd"].includedirs.append("included")
        deps_cpp_info.update(DepCppInfo(dep2), "dep2")

        self.assertListEqual([os.path.join(folder1, "include"), os.path.join(folder1, "includea"),
                              os.path.join(folder1, "includeb")],
                             deps_cpp_info["dep1"].include_paths)
        self.assertListEqual([os.path.join(folder2, "include"), os.path.join(folder2, "includec"),
                              os.path.join(folder2, "included")],
                             deps_cpp_info["dep2"].include_paths)
        self.assertListEqual([os.path.join(folder1, "include"), os.path.join(folder1, "includea"),
                              os.path.join(folder1, "includeb"), os.path.join(folder2, "include"),
                              os.path.join(folder2, "includec"), os.path.join(folder2, "included")],
                             deps_cpp_info.include_paths)

    def test_deps_cpp_info_libs_defines_flags(self):
        deps_cpp_info = DepsCppInfo()

        dep1 = CppInfo("root")
        dep1.components["liba"].libs.append("liba")
        dep1.components["liba"].defines.append("DEFINEA")
        dep1.components["liba"].system_libs.append("sysa")
        dep1.components["liba"].cxxflags.append("cxxflaga")
        dep1.components["liba"].cflags.append("cflaga")
        dep1.components["liba"].sharedlinkflags.append("slinka")
        dep1.components["liba"].frameworks.append("frameworka")
        dep1.components["liba"].exelinkflags.append("elinka")
        dep1.components["libb"].libs.append("libb")
        dep1.components["libb"].defines.append("DEFINEB")
        dep1.components["libb"].system_libs.append("sysb")
        dep1.components["libb"].cxxflags.append("cxxflagb")
        dep1.components["libb"].cflags.append("cflagb")
        dep1.components["libb"].sharedlinkflags.append("slinkb")
        dep1.components["libb"].frameworks.append("frameworkb")
        dep1.components["libb"].exelinkflags.append("elinkb")
        deps_cpp_info.update(DepCppInfo(dep1), "dep1")

        dep2 = CppInfo("root")
        dep2.components["libc"].libs.append("libc")
        dep2.components["libd"].libs.append("libd")
        dep2.components["systemlib"].system_libs = ["systemlib"]
        dep2.components["libc"].cxxflags = ["cxxflagc"]
        dep2.components["libd"].cflags = ["cflagd"]
        dep2.components["libc"].sharedlinkflags = ["slinkc"]
        dep2.components["libd"].sharedlinkflags = ["slinkd"]
        deps_cpp_info.update(DepCppInfo(dep2), "dep2")

        self.assertListEqual(["liba", "libb"], deps_cpp_info["dep1"].libs)
        self.assertListEqual(["libc", "libd"], deps_cpp_info["dep2"].libs)
        self.assertListEqual(["liba", "libb", "libc", "libd"], deps_cpp_info.libs)

        self.assertListEqual(["DEFINEA", "DEFINEB"], deps_cpp_info["dep1"].defines)
        self.assertListEqual(["DEFINEA", "DEFINEB"], deps_cpp_info.defines)

        self.assertListEqual(["sysa", "sysb"], deps_cpp_info["dep1"].system_libs)
        self.assertListEqual(["systemlib"], deps_cpp_info["dep2"].system_libs)
        self.assertListEqual(["sysa", "sysb", "systemlib"], deps_cpp_info.system_libs)

        self.assertListEqual(["cxxflaga", "cxxflagb"], deps_cpp_info["dep1"].cxxflags)
        self.assertListEqual(["cxxflagc"], deps_cpp_info["dep2"].cxxflags)
        self.assertListEqual(["cxxflagc", "cxxflaga", "cxxflagb"], deps_cpp_info.cxxflags)

        self.assertListEqual(["cflaga", "cflagb"], deps_cpp_info["dep1"].cflags)
        self.assertListEqual(["cflagd"], deps_cpp_info["dep2"].cflags)
        self.assertListEqual(["cflagd", "cflaga", "cflagb"], deps_cpp_info.cflags)

        self.assertListEqual(["slinka", "slinkb"], deps_cpp_info["dep1"].sharedlinkflags)
        self.assertListEqual(["slinkc", "slinkd"], deps_cpp_info["dep2"].sharedlinkflags)
        self.assertListEqual(["slinkc", "slinkd", "slinka", "slinkb"],
                             deps_cpp_info.sharedlinkflags)

        self.assertListEqual(["frameworka", "frameworkb"], deps_cpp_info["dep1"].frameworks)
        self.assertListEqual(["frameworka", "frameworkb"], deps_cpp_info.frameworks)

        self.assertListEqual(["elinka", "elinkb"], deps_cpp_info["dep1"].exelinkflags)
        self.assertListEqual([], deps_cpp_info["dep2"].exelinkflags)
        self.assertListEqual(["elinka", "elinkb"], deps_cpp_info.exelinkflags)

    def test_deps_cpp_info_libs_release_debug(self):
        deps_cpp_info = DepsCppInfo()

        dep1 = CppInfo("root")
        dep1.components["liba"].libs.append("liba")
        with self.assertRaises(AttributeError):
            dep1.release.components["libb"].libs.append("libb")
        with self.assertRaises(AttributeError):
            dep1.debug.components["libb"].libs.append("libb_d")
        deps_cpp_info.update(DepCppInfo(dep1), "dep1")

        dep2 = CppInfo("root")
        dep2.release.libs.append("libdep2")
        dep2.debug.libs.append("libdep2_d")
        with self.assertRaises(AttributeError):
            dep2.components["libc"].release.libs.append("libc")
        with self.assertRaises(AttributeError):
            dep2.components["libc"].debug.libs.append("libc_d")
        dep2.components["libc"].libs.append("libc")
        dep2.components["libc"].libs.append("libc2")
        deps_cpp_info.update(DepCppInfo(dep2), "dep2")

        self.assertListEqual(["liba"], deps_cpp_info["dep1"].libs)
        self.assertListEqual(["libc", "libc2"], deps_cpp_info["dep2"].libs)
        self.assertListEqual(["liba", "libc", "libc2"], deps_cpp_info.libs)

        self.assertListEqual([], deps_cpp_info["dep1"].release.libs)
        self.assertListEqual(["libdep2"], deps_cpp_info["dep2"].release.libs)
        self.assertListEqual(["libdep2"], deps_cpp_info.release.libs)

        self.assertListEqual([], deps_cpp_info["dep1"].debug.libs)
        self.assertListEqual(["libdep2_d"], deps_cpp_info["dep2"].debug.libs)
        self.assertListEqual(["libdep2_d"], deps_cpp_info.debug.libs)
