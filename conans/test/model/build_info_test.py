import unittest
import os
from conans.model.build_info import DepsCppInfo, CppInfo
from conans.client.generators import TXTGenerator
from collections import namedtuple, defaultdict
from conans.model.env_info import DepsEnvInfo, EnvInfo
from conans.model.user_info import DepsUserInfo
from conans.test.utils.test_files import temp_folder
import platform
from conans.util.files import mkdir


class BuildInfoTest(unittest.TestCase):

    def parse_test(self):
        text = """[includedirs]
C:/Whenever
[includedirs_Boost]
F:/ChildrenPath
[includedirs_My_Lib]
mylib_path
[includedirs_My_Other_Lib]
otherlib_path
[includedirs_My.Component.Lib]
my_component_lib
[includedirs_My-Component-Tool]
my-component-tool
        """
        deps_cpp_info, _, _ = TXTGenerator.loads(text)

        def assert_cpp(deps_cpp_info_test):
            self.assertEqual(deps_cpp_info_test.includedirs, ['C:/Whenever'])
            self.assertEqual(deps_cpp_info_test["Boost"].includedirs, ['F:/ChildrenPath'])
            self.assertEqual(deps_cpp_info_test["My_Lib"].includedirs, ['mylib_path'])
            self.assertEqual(deps_cpp_info_test["My_Other_Lib"].includedirs, ['otherlib_path'])
            self.assertEqual(deps_cpp_info_test["My-Component-Tool"].includedirs, ['my-component-tool'])

        assert_cpp(deps_cpp_info)
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
        deps_env_info = DepsEnvInfo()
        deps_cpp_info = DepsCppInfo()
        deps_cpp_info.includedirs.append("C:/whatever")
        deps_cpp_info.includedirs.append("C:/whenever")
        deps_cpp_info.libdirs.append("C:/other")
        deps_cpp_info.libs.extend(["math", "winsock", "boost"])
        child = DepsCppInfo()
        child.includedirs.append("F:/ChildrenPath")
        child.cppflags.append("cxxmyflag")
        deps_cpp_info._dependencies["Boost"] = child
        fakeconan = namedtuple("Conanfile", "deps_cpp_info cpp_info deps_env_info env_info user_info deps_user_info")
        output = TXTGenerator(fakeconan(deps_cpp_info, None, deps_env_info, None, {}, defaultdict(dict))).content
        deps_cpp_info2, _, _ = TXTGenerator.loads(output)
        self.assertEqual(deps_cpp_info.configs, deps_cpp_info2.configs)
        self.assertEqual(deps_cpp_info.includedirs, deps_cpp_info2.includedirs)
        self.assertEqual(deps_cpp_info.libdirs, deps_cpp_info2.libdirs)
        self.assertEqual(deps_cpp_info.bindirs, deps_cpp_info2.bindirs)
        self.assertEqual(deps_cpp_info.libs, deps_cpp_info2.libs)
        self.assertEqual(len(deps_cpp_info._dependencies),
                         len(deps_cpp_info2._dependencies))
        self.assertEqual(deps_cpp_info["Boost"].includedirs,
                         deps_cpp_info2["Boost"].includedirs)
        self.assertEqual(deps_cpp_info["Boost"].cppflags,
                         deps_cpp_info2["Boost"].cppflags)
        self.assertEqual(deps_cpp_info["Boost"].cppflags, ["cxxmyflag"])

    def configs_test(self):
        deps_cpp_info = DepsCppInfo()
        deps_cpp_info.includedirs.append("C:/whatever")
        deps_cpp_info.debug.includedirs.append("C:/whenever")
        deps_cpp_info.libs.extend(["math"])
        deps_cpp_info.debug.libs.extend(["debug_Lib"])

        child = DepsCppInfo()
        child.includedirs.append("F:/ChildrenPath")
        child.debug.includedirs.append("F:/ChildrenDebugPath")
        child.cppflags.append("cxxmyflag")
        child.debug.cppflags.append("cxxmydebugflag")
        deps_cpp_info._dependencies["Boost"] = child

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
        self.assertEqual(deps_cpp_info.includedirs, deps_cpp_info2.includedirs)
        self.assertEqual(deps_cpp_info.libdirs, deps_cpp_info2.libdirs)
        self.assertEqual(deps_cpp_info.bindirs, deps_cpp_info2.bindirs)
        self.assertEqual(deps_cpp_info.libs, deps_cpp_info2.libs)
        self.assertEqual(len(deps_cpp_info._dependencies),
                         len(deps_cpp_info2._dependencies))
        self.assertEqual(deps_cpp_info["Boost"].includedirs,
                         deps_cpp_info2["Boost"].includedirs)
        self.assertEqual(deps_cpp_info["Boost"].cppflags,
                         deps_cpp_info2["Boost"].cppflags)
        self.assertEqual(deps_cpp_info["Boost"].cppflags, ["cxxmyflag"])

        self.assertEqual(deps_cpp_info.debug.includedirs, deps_cpp_info2.debug.includedirs)
        self.assertEqual(deps_cpp_info.debug.includedirs, ["C:/whenever"])

        self.assertEqual(deps_cpp_info.debug.libs, deps_cpp_info2.debug.libs)
        self.assertEqual(deps_cpp_info.debug.libs, ["debug_Lib"])

        self.assertEqual(deps_cpp_info["Boost"].debug.includedirs,
                         deps_cpp_info2["Boost"].debug.includedirs)
        self.assertEqual(deps_cpp_info["Boost"].debug.includedirs,
                         ["F:/ChildrenDebugPath"])
        self.assertEqual(deps_cpp_info["Boost"].debug.cppflags,
                         deps_cpp_info2["Boost"].debug.cppflags)
        self.assertEqual(deps_cpp_info["Boost"].debug.cppflags, ["cxxmydebugflag"])

        self.assertEqual(deps_env_info["LIB1"].var, "32")
        self.assertEqual(deps_env_info["LIB1"].othervar, ["somevalue"])

        self.assertEqual(deps_user_info["LIB2"].myuservar, "23")

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
        self.assertEqual(info.include_paths, [os.path.join(folder, "include"), abs_include])
        self.assertEqual(info.lib_paths, [os.path.join(folder, "lib"), abs_lib])
        self.assertEqual(info.bin_paths, [abs_bin,
                                          os.path.join(folder, "local_bindir")])
