import unittest
import os
from conans.model.build_info import DepsCppInfo, CppInfo
from conans.client.generators import TXTGenerator
from collections import namedtuple
from conans.model.env_info import DepsEnvInfo
from conans.test.utils.test_files import temp_folder
import platform


class BuildInfoTest(unittest.TestCase):

    def _equal(self, item1, item2):
        for field in item1.fields:
            self.assertEqual(getattr(item1, field),
                             getattr(item2, field))

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
        self._equal(deps_cpp_info, deps_cpp_info2)

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
