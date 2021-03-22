import unittest

from mock import Mock

from conans.client.generators.text import TXTGenerator
from conans.model.build_info import CppInfo, DepCppInfo
from conans.model.conan_file import ConanFile
from conans.model.env_info import EnvValues, EnvInfo
from conans.model.ref import ConanFileReference
from conans.model.settings import Settings
from conans.model.user_info import DepsUserInfo
from conans.model.user_info import UserInfo


class DumpLoadTestCase(unittest.TestCase):

    def test_names_per_generator(self):
        cpp_info = CppInfo("pkg_name", "root")
        cpp_info.name = "name"
        cpp_info.names["txt"] = "txt_name"
        cpp_info.names["cmake_find_package"] = "SpecialName"
        cpp_info.filenames["cmake_find_package"] = "SpecialFileName"
        conanfile = ConanFile(Mock(), None)
        conanfile.initialize(Settings({}), EnvValues())
        conanfile.deps_cpp_info.add("pkg_name", DepCppInfo(cpp_info))
        content = TXTGenerator(conanfile).content
        parsed_deps_cpp_info, _, _, _ = TXTGenerator.loads(content, filter_empty=False)

        parsed_cpp_info = parsed_deps_cpp_info["pkg_name"]
        self.assertEqual(parsed_cpp_info.get_name("txt"), "txt_name")
        self.assertEqual(parsed_cpp_info.get_name("cmake_find_package"), "SpecialName")
        self.assertEqual(parsed_cpp_info.get_filename("cmake_find_package"), "SpecialFileName")
        self.assertEqual(parsed_cpp_info.get_name("pkg_config"), "pkg_name")

    def test_idempotent(self):
        conanfile = ConanFile(Mock(), None)
        conanfile.initialize(Settings({}), EnvValues())

        # Add some cpp_info
        ref = ConanFileReference.loads("MyPkg/0.1@lasote/stables")
        cpp_info = CppInfo(ref.name, "dummy_root_folder1")
        cpp_info.names["txt"] = "mypkg1-txt"
        cpp_info.version = ref.version
        cpp_info.defines = ["MYDEFINE1"]
        cpp_info.cxxflags = ["-cxxflag_parent"]
        cpp_info.includedirs = ["mypkg1/include"]
        cpp_info.filter_empty = False
        conanfile.deps_cpp_info.add(ref.name, cpp_info)

        ref = ConanFileReference.loads("MyPkg2/0.1@lasote/stables")
        cpp_info = CppInfo(ref.name, "dummy_root_folder2")
        cpp_info.defines = ["MYDEFINE2"]
        cpp_info.cxxflags = ["-cxxflag_dep"]
        cpp_info.filter_empty = False
        conanfile.deps_cpp_info.add(ref.name, cpp_info)

        # Add env_info
        env_info = EnvInfo()
        env_info.VAR1 = "value1"
        env_info.PATH.append("path-extended")
        conanfile.deps_env_info.update(env_info, "my_pkg")

        env_info = EnvInfo()
        env_info.VAR1 = "other-value1"
        env_info.PATH.append("other-path-extended")
        conanfile.deps_env_info.update(env_info, "other-pkg")

        # Add user_info for HOST
        user_info = UserInfo()
        user_info.VAR1 = "value1"
        conanfile.deps_user_info["my_pkg"] = user_info

        user_info = UserInfo()
        user_info.VAR1 = "other-value1"
        conanfile.deps_user_info["other-pkg"] = user_info

        # Add user_info for BUILD
        conanfile.user_info_build = DepsUserInfo()
        user_info = UserInfo()
        user_info.VAR1 = "value1"
        conanfile.user_info_build["build_pkg"] = user_info

        user_info = UserInfo()
        user_info.VAR1 = "other-value1"
        conanfile.user_info_build["other-build-pkg"] = user_info

        master_content = TXTGenerator(conanfile).content
        after_cpp_info, after_user_info, after_env_info, after_user_info_build = \
            TXTGenerator.loads(master_content, filter_empty=False)
        # Assign them to a different conanfile
        other_conanfile = ConanFile(Mock(), None)
        other_conanfile.initialize(Settings({}), EnvValues())
        other_conanfile.deps_cpp_info = after_cpp_info
        other_conanfile.deps_env_info = after_env_info
        other_conanfile.deps_user_info = after_user_info
        other_conanfile.user_info_build = after_user_info_build
        after_content = TXTGenerator(other_conanfile).content

        self.assertListEqual(master_content.splitlines(), after_content.splitlines())
