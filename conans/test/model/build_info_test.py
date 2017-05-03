import unittest
import os
from conans.model.build_info import DepsCppInfo, CppInfo
from conans.client.generators import TXTGenerator
from collections import namedtuple
from conans.model.env_info import DepsEnvInfo
from conans.test.utils.test_files import temp_folder
import platform


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
        """
        deps_info = DepsCppInfo.loads(text)
        self.assertEqual(deps_info.includedirs, ['C:/Whenever'])
        self.assertEqual(deps_info["Boost"].includedirs, ['F:/ChildrenPath'])
        self.assertEqual(deps_info["My_Lib"].includedirs, ['mylib_path'])
        self.assertEqual(deps_info["My_Other_Lib"].includedirs, ['otherlib_path'])

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
        fakeconan = namedtuple("Conanfile", "deps_cpp_info cpp_info deps_env_info env_info")
        output = TXTGenerator(fakeconan(deps_cpp_info, None, deps_env_info, None)).content
        deps_cpp_info2 = DepsCppInfo.loads(output)
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

        fakeconan = namedtuple("Conanfile", "deps_cpp_info cpp_info deps_env_info env_info")
        output = TXTGenerator(fakeconan(deps_cpp_info, None, None, None)).content

        deps_cpp_info2 = DepsCppInfo.loads(output)
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

    def cpp_info_test(self):
        folder = temp_folder()
        info = CppInfo(folder)
        info.includedirs.append("/usr/include")
        info.libdirs.append("/usr/lib")
        bin_abs_dir = "C:/usr/bin" if platform.system() == "Windows" else "/tmp"
        info.bindirs.append(bin_abs_dir)
        info.bindirs.append("local_bindir")
        self.assertEqual(info.include_paths, [os.path.join(folder, "include"), "/usr/include"])
        self.assertEqual(info.lib_paths, [os.path.join(folder, "lib"), "/usr/lib"])
        self.assertEqual(info.bin_paths, [os.path.join(folder, "bin"), bin_abs_dir,
                                          os.path.join(folder, "local_bindir")])
