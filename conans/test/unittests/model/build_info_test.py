import os
import platform

import six
import unittest
from collections import defaultdict, namedtuple, OrderedDict

from conans.client.generators import TXTGenerator
from conans.errors import ConanException
from conans.model.build_info import CppInfo, DepsCppInfo, Component, DepCppInfo
from conans.model.build_info_components import DepComponent
from conans.model.env_info import DepsEnvInfo, EnvInfo
from conans.model.user_info import DepsUserInfo
from conans.test.utils.conanfile import MockConanfile
from conans.test.utils.deprecation import catch_deprecation_warning, catch_real_deprecation_warning
from conans.test.utils.test_files import temp_folder
from conans.util.files import mkdir, save


def _normpaths(paths):
    return [os.path.normpath(path) for path in paths]


class BuildInfoTest(unittest.TestCase):

    def parse_test(self):
        items = [
"""
[rootpath_Boost]
/this_boost_path
""",
"""
[rootpath_My_Lib]
/this_my_lib_path
""",
"""
[rootpath_My_Other_Lib]
/this_my_other_lib_path
""",
"""
[rootpath_My.Component.Lib]
/this_my_component_lib_path
""",
"""
[rootpath_My-Component-Tool]
/this_my_component_tool_path
""",
"""
[includedirs_Boost]
F:/ChildrenPath
""" if platform.system() == "Windows" else """
[includedirs_Boost]
/ChildrenPath
""",
"""
[includedirs_My_Lib]
/this_my_lib_path/mylib_path
""",
"""
[includedirs_My_Other_Lib]
/this_my_other_lib_path/otherlib_path
""",
"""
[includedirs_My.Component.Lib]
/this_my_component_lib_path/my_component_lib
""",
"""
[includedirs_My-Component-Tool]
/this_my_component_tool_path/my-component-tool
"""]
        text = "".join(items)
        deps_cpp_info, _, _ = TXTGenerator.loads(text)

        def assert_cpp(deps_cpp_info_test):
            children_abs_path = "F:/ChildrenPath" if platform.system() == "Windows" else\
                "/ChildrenPath"
            self.assertEqual([children_abs_path, 'mylib_path', 'otherlib_path', 'my_component_lib',
                              'my-component-tool'], deps_cpp_info_test.includedirs)
            self.assertEqual([children_abs_path], deps_cpp_info_test["Boost"].includedirs)
            self.assertEqual(['mylib_path'], deps_cpp_info_test["My_Lib"].includedirs)
            self.assertEqual(['otherlib_path'], deps_cpp_info_test["My_Other_Lib"].includedirs)
            self.assertEqual(['my-component-tool'],
                             deps_cpp_info_test["My-Component-Tool"].includedirs)
            self.assertIn(os.path.join('/this_my_lib_path', 'mylib_path'),
                          deps_cpp_info_test.include_paths)
            self.assertIn(os.path.join('/this_my_component_lib_path', 'my_component_lib'),
                          deps_cpp_info_test.include_paths)
            self.assertIn(os.path.join('/this_my_component_tool_path', 'my-component-tool'),
                          deps_cpp_info_test.include_paths)
            self.assertIn(children_abs_path, deps_cpp_info_test.include_paths)
            self.assertIn(os.path.join('/this_my_other_lib_path', 'otherlib_path'),
                          deps_cpp_info_test.include_paths)
            self.assertEqual([children_abs_path],
                             deps_cpp_info_test["Boost"].include_paths)
            self.assertEqual([os.path.join('/this_my_lib_path', 'mylib_path')],
                             deps_cpp_info_test["My_Lib"].include_paths)
            self.assertEqual([os.path.join('/this_my_other_lib_path', 'otherlib_path')],
                             deps_cpp_info_test["My_Other_Lib"].include_paths)
            self.assertEqual([os.path.join('/this_my_component_tool_path', 'my-component-tool')],
                             deps_cpp_info_test["My-Component-Tool"].include_paths)

        assert_cpp(deps_cpp_info)
        # Test generated content is the same
        conanfile = MockConanfile(None)
        conanfile.display_name = "name"
        conanfile.deps_cpp_info = deps_cpp_info
        conanfile.deps_env_info = DepsEnvInfo()
        conanfile.deps_user_info = DepsUserInfo()
        conanfile.env_info = EnvInfo()
        txt_generator = TXTGenerator(conanfile)
        for item in items:
            self.assertIn(item, txt_generator.content)

        # Now adding env_info
        text2 = text + """
[ENV_LIBA]
VAR2=23
"""
        deps_cpp_info, _, deps_env_info = TXTGenerator.loads(text2)
        assert_cpp(deps_cpp_info)
        self.assertEqual(deps_env_info["LIBA"].VAR2, "23")

        # Now only with user info
        text3 = text + """
[USER_LIBA]
VAR2=23
"""
        deps_cpp_info, deps_user_info, _ = TXTGenerator.loads(text3)
        assert_cpp(deps_cpp_info)
        self.assertEqual(deps_user_info["LIBA"].VAR2, "23")

        # Now with all
        text4 = text + """
[USER_LIBA]
VAR2=23

[ENV_LIBA]
VAR2=23
"""
        deps_cpp_info, deps_user_info, deps_env_info = TXTGenerator.loads(text4)
        assert_cpp(deps_cpp_info)
        self.assertEqual(deps_user_info["LIBA"].VAR2, "23")
        self.assertEqual(deps_env_info["LIBA"].VAR2, "23")

    def help_test(self):
        whatever_abs_path = "C:/whatever" if platform.system() == "Windows" else "/whatever"
        whenever_abs_path = "C:/whenever" if platform.system() == "Windows" else "/whenever"
        deps_env_info = DepsEnvInfo()
        deps_cpp_info = DepsCppInfo()
        one_dep_folder = temp_folder()
        one_dep = CppInfo(one_dep_folder)
        one_dep.filter_empty = False  # For testing: Do not filter paths
        one_dep.includedirs.append(whatever_abs_path)
        one_dep.includedirs.append(whenever_abs_path)
        one_dep.libdirs.append("other")
        one_dep.libs.extend(["math", "winsock", "boost"])
        deps_cpp_info.update(one_dep, "global")
        child_folder = temp_folder()
        child = CppInfo(child_folder)
        child.filter_empty = False  # For testing: Do not filter paths
        child.includedirs.append("ChildrenPath")
        child.cxxflags.append("cxxmyflag")
        deps_cpp_info.update(child, "Boost")
        self.assertEqual([os.path.join(one_dep_folder, "include"),
                          whatever_abs_path,
                          whenever_abs_path,
                          os.path.join(child_folder, "include"),
                          os.path.join(child_folder, "ChildrenPath")], deps_cpp_info.include_paths)
        fakeconan = namedtuple("Conanfile", "deps_cpp_info cpp_info deps_env_info env_info user_info deps_user_info")
        output = TXTGenerator(fakeconan(deps_cpp_info, None, deps_env_info, None, {}, defaultdict(dict))).content
        deps_cpp_info2, _, _ = TXTGenerator.loads(output)
        self.assertEqual(deps_cpp_info.configs, deps_cpp_info2.configs)
        self.assertEqual(_normpaths(deps_cpp_info.include_paths),
                         _normpaths(deps_cpp_info2.include_paths))
        self.assertEqual(_normpaths(deps_cpp_info.lib_paths),
                         _normpaths(deps_cpp_info2.lib_paths))
        self.assertEqual(_normpaths(deps_cpp_info.lib_paths),
                         _normpaths(deps_cpp_info2.lib_paths))
        self.assertEqual(deps_cpp_info.libs, deps_cpp_info2.libs)
        self.assertEqual(len(deps_cpp_info._dependencies),
                         len(deps_cpp_info2._dependencies))
        self.assertEqual(_normpaths(deps_cpp_info["Boost"].include_paths),
                         _normpaths(deps_cpp_info2["Boost"].include_paths))
        self.assertEqual(deps_cpp_info["Boost"].cxxflags,
                         deps_cpp_info2["Boost"].cxxflags)
        self.assertEqual(deps_cpp_info["Boost"].cxxflags, ["cxxmyflag"])

    def configs_test(self):
        whatever_abs_path = "C:/whatever" if platform.system() == "Windows" else "/whatever"
        whenever_abs_path = "C:/whenever" if platform.system() == "Windows" else "/whenever"
        deps_cpp_info = DepsCppInfo()
        parent_folder = temp_folder()
        parent = CppInfo(parent_folder)
        parent.filter_empty = False  # For testing: Do not remove empty paths
        parent.includedirs.append(whatever_abs_path)
        self.assertEqual({}, parent.configs)
        parent.debug.includedirs.append(whenever_abs_path)
        self.assertEqual(["debug"], list(parent.configs))
        parent.libs.extend(["math"])
        parent.debug.libs.extend(["debug_Lib"])
        self.assertEqual(["debug"], list(parent.configs))
        dep_cpp_info_parent = DepCppInfo(parent)
        deps_cpp_info.update_dep_cpp_info(dep_cpp_info_parent, "parent")
        self.assertEqual(["debug"], list(deps_cpp_info.configs))
        self.assertEqual(os.path.join(parent_folder, "include"),
                         deps_cpp_info.debug.include_paths[0])
        self.assertEqual(whenever_abs_path, deps_cpp_info.debug.include_paths[1])
        self.assertEqual(os.path.join(parent_folder, "include"),
                         deps_cpp_info.include_paths[0])
        self.assertEqual(whatever_abs_path, deps_cpp_info.include_paths[1])

        children_abs_path = "C:/ChildrenPath" if platform.system() == "Windows" else "/ChildrenPath"
        children_debug_abs_path = "C:/ChildrenDebugPath" if platform.system() == "Windows" else \
            "/ChildrenDebugPath"
        child_folder = temp_folder()
        child = CppInfo(child_folder)
        child.filter_empty = False  # For testing: Do not remove empty paths
        child.includedirs.append(children_abs_path)
        child.debug.includedirs.append(children_debug_abs_path)
        child.cxxflags.append("cxxmyflag")
        child.debug.cxxflags.append("cxxmydebugflag")
        deps_cpp_info.update(child, "child")

        self.assertEqual([os.path.join(parent_folder, "include"),
                          whenever_abs_path,
                          os.path.join(child_folder, "include"),
                          children_debug_abs_path],
                         deps_cpp_info.debug.include_paths)
        self.assertEqual(["cxxmyflag"], deps_cpp_info["child"].cxxflags)
        self.assertEqual(["debug_Lib"], deps_cpp_info.debug.libs)

        self.assertEqual([os.path.join(parent_folder, "include"),
                          whatever_abs_path,
                          os.path.join(child_folder, "include"),
                          children_abs_path],
                         deps_cpp_info.include_paths)

        deps_env_info = DepsEnvInfo()
        env_info_lib1 = EnvInfo()
        env_info_lib1.var = "32"
        env_info_lib1.othervar.append("somevalue")
        deps_env_info.update(env_info_lib1, "LIB1")

        deps_user_info = DepsUserInfo()
        deps_user_info["LIB2"].myuservar = "23"

        fakeconan = namedtuple("Conanfile", "deps_cpp_info cpp_info deps_env_info env_info user_info deps_user_info")
        output = TXTGenerator(fakeconan(deps_cpp_info, None, deps_env_info, deps_user_info, {}, defaultdict(dict))).content

        deps_cpp_info2, _, deps_env_info2 = TXTGenerator.loads(output)
        self.assertEqual([os.path.join(parent_folder, "include"),
                          whatever_abs_path,
                          os.path.join(child_folder, "include"),
                          children_abs_path], deps_cpp_info.include_paths)
        self.assertEqual(_normpaths(deps_cpp_info.include_paths),
                         _normpaths(deps_cpp_info2.include_paths))
        self.assertEqual(_normpaths(deps_cpp_info.lib_paths),
                         _normpaths(deps_cpp_info2.lib_paths))
        self.assertEqual(_normpaths(deps_cpp_info.bin_paths),
                         _normpaths(deps_cpp_info2.bin_paths))
        self.assertEqual(deps_cpp_info.libs, deps_cpp_info2.libs)
        self.assertEqual(len(deps_cpp_info._dependencies), len(deps_cpp_info2._dependencies))
        self.assertEqual(_normpaths(deps_cpp_info["parent"].include_paths),
                         _normpaths(deps_cpp_info2["parent"].include_paths))
        self.assertEqual(deps_cpp_info["parent"].cxxflags, deps_cpp_info2["parent"].cxxflags)

        self.assertEqual(_normpaths(deps_cpp_info.debug.include_paths),
                         _normpaths(deps_cpp_info2.debug.include_paths))

        self.assertEqual(deps_cpp_info.debug.libs, deps_cpp_info2.debug.libs)

        self.assertEqual(_normpaths(deps_cpp_info["child"].debug.include_paths),
                         _normpaths(deps_cpp_info2["child"].debug.include_paths))
        self.assertEqual(_normpaths([os.path.join(child_folder, "include"),
                                     children_debug_abs_path]),
                         _normpaths(deps_cpp_info["child"].debug.include_paths))
        self.assertEqual(deps_cpp_info["child"].debug.cxxflags,
                         deps_cpp_info2["child"].debug.cxxflags)
        self.assertEqual(deps_cpp_info["child"].debug.cxxflags, ["cxxmydebugflag"])

        self.assertEqual("32", deps_env_info2["LIB1"].var)
        self.assertEqual(["somevalue"], deps_env_info2["LIB1"].othervar)

    def cpp_info_test(self):
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
        info = CppInfo(folder)
        info.includedirs.append(abs_include)
        info.libdirs.append(abs_lib)
        info.bindirs.append(abs_bin)
        info.bindirs.append("local_bindir")
        info = DepCppInfo(info)
        self.assertEqual(info.include_paths, [os.path.join(folder, "include"), abs_include])
        self.assertEqual(info.lib_paths, [os.path.join(folder, "lib"), abs_lib])
        self.assertEqual(info.bin_paths, [abs_bin,
                                          os.path.join(folder, "local_bindir")])

    def basic_components_test(self):
        cpp_info = CppInfo(None)
        component = cpp_info["my_component"]
        self.assertEqual(component.name, "my_component")
        component.lib = "libhola"
        self.assertEqual(component.lib, "libhola")
        with six.assertRaisesRegex(self, ConanException, "'.lib' is already set for this Component"):
            component.exe = "hola.exe"

        component = cpp_info["my_other_component"]
        component.exe = "hola.exe"
        self.assertEqual(component.lib, None)
        with six.assertRaisesRegex(self, ConanException, "'.exe' is already set for this Component"):
            component.lib = "libhola"

    def cpp_info_libs_components_fail_test(self):
        """
        Usage of .libs is not allowed in cpp_info when using Components
        """
        info = CppInfo(None)
        info.name = "Greetings"
        self.assertEqual(info.name, "Greetings")
        info.libs = ["libgreet"]
        with six.assertRaisesRegex(self, ConanException, "Using Components and global 'libs' "
                                                         "values"):
            info["hola"].exe = "hola.exe"

        info.libs = []
        info["greet"].exe = "exegreet"

    def cpp_info_system_deps_test(self):
        """
        System deps are composed in '.libs' attribute even if there are no '.lib' in the component.
        Also make sure None values are discarded.
        """
        info = CppInfo("")
        info["LIB1"].system_deps = ["sys1", "sys11"]
        info["LIB1"].deps = ["LIB2"]
        info["LIB2"].system_deps = ["sys2"]
        info["LIB2"].deps = ["LIB3"]
        info["LIB3"].system_deps = ["sys3", "sys2"]
        self.assertEqual(['sys1', 'sys11', 'sys2', 'sys3', 'sys2'], DepCppInfo(info).libs)
        self.assertEqual(['sys1', 'sys11', 'sys2', 'sys3', 'sys2'], DepCppInfo(info).system_deps)
        info["LIB3"].system_deps = [None, "sys2"]
        self.assertEqual(['sys1', 'sys11', 'sys2', 'sys2'], DepCppInfo(info).libs)
        self.assertEqual(['sys1', 'sys11', 'sys2', 'sys2'], DepCppInfo(info).system_deps)

    def cpp_info_libs_system_deps_order_test(self):
        """
        Check the order of libs and system_deps and discard repeated values
        """
        info = CppInfo("")
        info["LIB1"].lib = "lib1"
        info["LIB1"].system_deps = ["sys1", "sys11"]
        info["LIB1"].deps = ["LIB2"]
        info["LIB2"].lib = "lib2"
        info["LIB2"].system_deps = ["sys2"]
        info["LIB2"].deps = ["LIB3"]
        info["LIB3"].lib = "lib3"
        info["LIB3"].system_deps = ["sys3", "sys2"]
        dep_info = DepCppInfo(info)
        self.assertEqual(['lib1', 'sys1', 'sys11', 'lib2', 'sys2', 'lib3', 'sys3', 'sys2'],
                         dep_info.libs)
        self.assertEqual(['sys1', 'sys11', 'sys2', 'sys3', 'sys2'], dep_info.system_deps)

    def cpp_info_link_order_test(self):

        def _assert_link_order(sorted_libs):
            """
            Assert that dependent libs of a component are always found later in the list
            """
            assert sorted_libs, "'sorted_libs' is empty"
            for num, lib in enumerate(sorted_libs):
                component_name = lib[-1]
                for dep in info[component_name].deps:
                    self.assertIn(info[dep].lib, sorted_libs[num:])

        info = CppInfo("")
        info["F"].lib = "libF"
        info["F"].deps = ["D", "E"]
        info["E"].lib = "libE"
        info["E"].deps = ["B"]
        info["D"].lib = "libD"
        info["D"].deps = ["A"]
        info["C"].lib = "libC"
        info["C"].deps = ["A"]
        info["A"].lib = "libA"
        info["A"].deps = ["B"]
        info["B"].lib = "libB"
        info["B"].deps = []
        _assert_link_order(DepCppInfo(info).libs)
        self.assertEqual(["libC", "libF", "libD", "libA", "libE", "libB"], DepCppInfo(info).libs)

        info = CppInfo("")
        info["K"].lib = "libK"
        info["K"].deps = ["G", "H"]
        info["J"].lib = "libJ"
        info["J"].deps = ["F"]
        info["G"].lib = "libG"
        info["G"].deps = ["F"]
        info["H"].lib = "libH"
        info["H"].deps = ["F", "E"]
        info["L"].lib = "libL"
        info["L"].deps = ["I"]
        info["F"].lib = "libF"
        info["F"].deps = ["C", "D"]
        info["I"].lib = "libI"
        info["I"].deps = ["E"]
        info["C"].lib = "libC"
        info["C"].deps = ["A"]
        info["D"].lib = "libD"
        info["D"].deps = ["A"]
        info["E"].lib = "libE"
        info["E"].deps = ["A", "B"]
        info["A"].lib = "libA"
        info["A"].deps = []
        info["B"].lib = "libB"
        info["B"].deps = []
        _assert_link_order(DepCppInfo(info).libs)
        self.assertEqual(["libL", "libI", "libK", "libH", "libE", "libB", "libG", "libJ", "libF",
                          "libD", "libC", "libA"], DepCppInfo(info).libs)

    def cppinfo_inexistent_component_dep_test(self):
        info = CppInfo(None)
        info["LIB1"].lib = "lib1"
        info["LIB1"].deps = ["LIB2"]
        with six.assertRaisesRegex(self, ConanException, "Component 'LIB1' "
                                                         "declares a missing dependency"):
            DepCppInfo(info).libs

    def cpp_info_components_dep_loop_test(self):
        info = CppInfo(None)
        info["LIB1"].lib = "lib1"
        info["LIB1"].deps = ["LIB1"]
        msg = "There is a dependency loop in the components declared in 'self.cpp_info'"
        with six.assertRaisesRegex(self, ConanException, msg):
            DepCppInfo(info).libs
        info = CppInfo(None)
        info["LIB1"].lib = "lib1"
        info["LIB1"].deps = ["LIB2"]
        info["LIB2"].lib = "lib2"
        info["LIB2"].deps = ["LIB1", "LIB2"]
        with six.assertRaisesRegex(self, ConanException, msg):
            DepCppInfo(info).build_paths
        info = CppInfo(None)
        info["LIB1"].lib = "lib1"
        info["LIB1"].deps = ["LIB2"]
        info["LIB2"].lib = "lib2"
        info["LIB2"].deps = ["LIB3"]
        info["LIB3"].lib = "lib3"
        info["LIB3"].deps = ["LIB1"]
        with six.assertRaisesRegex(self, ConanException, msg):
            DepCppInfo(info).defines

    def cppinfo_dirs_test(self):
        folder = temp_folder()
        info = CppInfo(folder)
        info.name = "OpenSSL"
        info["OpenSSL"].includedirs = ["include"]
        info["OpenSSL"].libdirs = ["lib"]
        info["OpenSSL"].builddirs = ["build"]
        info["OpenSSL"].bindirs = ["bin"]
        info["OpenSSL"].resdirs = ["res"]
        info["Crypto"].includedirs = ["headers"]
        info["Crypto"].libdirs = ["libraries"]
        info["Crypto"].builddirs = ["build_scripts"]
        info["Crypto"].bindirs = ["binaries"]
        info["Crypto"].resdirs = ["resources"]
        self.assertEqual(["include"], info["OpenSSL"].includedirs)
        self.assertEqual(["lib"], info["OpenSSL"].libdirs)
        self.assertEqual(["build"], info["OpenSSL"].builddirs)
        self.assertEqual(["bin"], info["OpenSSL"].bindirs)
        self.assertEqual(["res"], info["OpenSSL"].resdirs)
        self.assertEqual(["headers"], info["Crypto"].includedirs)
        self.assertEqual(["libraries"], info["Crypto"].libdirs)
        self.assertEqual(["build_scripts"], info["Crypto"].builddirs)
        self.assertEqual(["binaries"], info["Crypto"].bindirs)
        self.assertEqual(["resources"], info["Crypto"].resdirs)

        info["Crypto"].includedirs = ["different_include"]
        info["Crypto"].libdirs = ["different_lib"]
        info["Crypto"].builddirs = ["different_build"]
        info["Crypto"].bindirs = ["different_bin"]
        info["Crypto"].resdirs = ["different_res"]
        self.assertEqual(["different_include"], info["Crypto"].includedirs)
        self.assertEqual(["different_lib"], info["Crypto"].libdirs)
        self.assertEqual(["different_build"], info["Crypto"].builddirs)
        self.assertEqual(["different_bin"], info["Crypto"].bindirs)
        self.assertEqual(["different_res"], info["Crypto"].resdirs)

        info["Crypto"].includedirs.extend(["another_include"])
        info["Crypto"].includedirs.append("another_other_include")
        info["Crypto"].libdirs.extend(["another_lib"])
        info["Crypto"].libdirs.append("another_other_lib")
        info["Crypto"].builddirs.extend(["another_build"])
        info["Crypto"].builddirs.append("another_other_build")
        info["Crypto"].bindirs.extend(["another_bin"])
        info["Crypto"].bindirs.append("another_other_bin")
        info["Crypto"].resdirs.extend(["another_res"])
        info["Crypto"].resdirs.append("another_other_res")
        self.assertEqual(["different_include", "another_include", "another_other_include"],
                         info["Crypto"].includedirs)
        self.assertEqual(["different_lib", "another_lib", "another_other_lib"],
                         info["Crypto"].libdirs)
        self.assertEqual(["different_build", "another_build", "another_other_build"],
                         info["Crypto"].builddirs)
        self.assertEqual(["different_bin", "another_bin", "another_other_bin"],
                         info["Crypto"].bindirs)
        self.assertEqual(["different_res", "another_res", "another_other_res"],
                         info["Crypto"].resdirs)

    def cppinfo_exes_test(self):
        info = CppInfo("")
        info.name = "OpenSSL"
        info["Exe1"].exe = "the_exe1"
        info["Exe2"].exe = "the_exe2"
        dep_info = DepCppInfo(info)
        self.assertEqual(["the_exe1", "the_exe2"], dep_info.exes)

    def cppinfo_public_interface_test(self):
        folder = temp_folder()
        info = CppInfo(folder)
        self.assertEqual([], info.exes)
        self.assertEqual([], info.libs)
        self.assertEqual([], info.system_deps)
        self.assertEqual(["include"], info.includedirs)
        self.assertEqual([], info.srcdirs)
        self.assertEqual(["res"], info.resdirs)
        self.assertEqual([""], info.builddirs)
        self.assertEqual(["bin"], info.bindirs)
        self.assertEqual(["lib"], info.libdirs)
        self.assertEqual(folder, info.rootpath)
        self.assertEqual([], info.defines)
        self.assertIsNone(info.name)
        self.assertEqual("", info.sysroot)
        self.assertEqual([], info.cflags)
        self.assertEqual({}, info.configs)  # FIXME: Make attr protected
        with catch_real_deprecation_warning(self):
            self.assertEqual([], info.cppflags)
        self.assertEqual([], info.cxxflags)
        self.assertEqual([], info.exelinkflags)
        with catch_real_deprecation_warning(self):
            self.assertEqual([], info.get_cppflags())  # FIXME: : Make method protected
        self.assertEqual([], info.public_deps)  # FIXME: Make attr protected
        with catch_real_deprecation_warning(self):
            info.set_cppflags("kk")  # FIXME: Make method protected
        self.assertEqual([], info.sharedlinkflags)

    def deps_cpp_info_components_test(self):
        folder = temp_folder()
        info = CppInfo(folder)
        save(os.path.join(folder, "include", "my_file.h"), "")  # Create file so path is not cleared
        info["Component"].lib = "libcomp"
        deps_cpp_info = DepsCppInfo()
        deps_cpp_info.update(info, "my_lib")
        self.assertEqual("libcomp", deps_cpp_info["my_lib"]["Component"].lib)
        self.assertEqual([os.path.join(folder, "include")], deps_cpp_info.include_paths)

    def deps_cpp_info_dirs_test(self):
        folder = temp_folder()
        info = CppInfo(folder)
        info["Component"]
        deps_cpp_info = DepsCppInfo()
        deps_cpp_info.update(info, "my_lib")
        self.assertEqual(["include"], deps_cpp_info.includedirs)
        self.assertEqual([], deps_cpp_info.srcdirs)
        self.assertEqual(["lib"], deps_cpp_info.libdirs)
        self.assertEqual(["bin"], deps_cpp_info.bindirs)
        self.assertEqual([""], deps_cpp_info.builddirs)
        self.assertEqual(["res"], deps_cpp_info.resdirs)

    def components_json_test(self):
        component = Component("com1", "folder")
        component.filter_empty = False
        dep_component = DepComponent(component)
        expected = {"name": "com1",
                    "rootpath": "folder",
                    "deps": [],
                    "lib": None,
                    "exe": None,
                    "system_deps": [],
                    "includedirs": ["include"],
                    "srcdirs": [],
                    "libdirs": ["lib"],
                    "bindirs": ["bin"],
                    "builddirs": [""],
                    "resdirs": ["res"],
                    "defines": [],
                    "cflags": [],
                    "cxxflags": [],
                    "sharedlinkflags": [],
                    "exelinkflags": []
                    }
        self.assertEqual(expected, component.as_dict())
        expected.update({
            "include_paths": [os.path.join("folder", "include")],
            "src_paths": [],
            "lib_paths": [os.path.join("folder", "lib")],
            "bin_paths": [os.path.join("folder", "bin")],
            "build_paths": [os.path.join("folder", "")],
            "res_paths": [os.path.join("folder", "res")],
        })
        self.assertEqual(expected, dep_component.as_dict())

    def deps_cpp_info_sysroot_test(self):
        """
        Sysroot should have the value set by the most direct dependency
        """
        folder = temp_folder()
        info = CppInfo(folder)
        info.sysroot = "hola"
        deps_cpp_info = DepsCppInfo()
        deps_cpp_info.update(info, "my_lib")
        self.assertEqual("hola", deps_cpp_info.sysroot)
        other_info = CppInfo(folder)
        other_info.sysroot = "kk"
        deps_cpp_info.update(other_info, "my_other_lib")
        self.assertEqual("hola", deps_cpp_info.sysroot)

    def deps_cpp_info_cflags_test(self):
        """
        Order of nodes in the graph is computed from bottom (node with more depdendencies) to top
        (node with no dependencies). Order of flags should be from less dependent to the most
        dependent one.
        """
        folder = temp_folder()
        info = CppInfo(folder)
        info.cflags = ["my_lib_flag"]
        deps_cpp_info = DepsCppInfo()
        deps_cpp_info.update(info, "my_lib")
        self.assertEqual(["my_lib_flag"], deps_cpp_info.cflags)
        other_info = CppInfo(folder)
        other_info.cflags = ["my_other_lib_flag"]
        deps_cpp_info.update(other_info, "my_other_lib")
        self.assertEqual(["my_other_lib_flag", "my_lib_flag"], deps_cpp_info.cflags)

    def components_with_configs_test(self):
        """
        Components can be part of one configuration (Release/Debug)
        """
        folder = temp_folder()
        info = CppInfo(folder)
        info.debug["DebugComponent"].lib = "libdebugcomp"
        deps_cpp_info = DepsCppInfo()
        deps_cpp_info.update(info, "my_lib")
        self.assertFalse(deps_cpp_info["my_lib"].components)
        self.assertEqual("libdebugcomp", deps_cpp_info["my_lib"].debug["DebugComponent"].lib)
