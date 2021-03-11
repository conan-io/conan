import textwrap
import unittest

from mock import Mock

from conans.client.generators.text import TXTGenerator
from conans.model.build_info import CppInfo
from conans.model.conan_file import ConanFile
from conans.model.env_info import EnvValues, EnvInfo
from conans.model.ref import ConanFileReference
from conans.model.settings import Settings
from conans.model.user_info import DepsUserInfo
from conans.model.user_info import UserInfo


class ConentGenerationTestCase(unittest.TestCase):

    def test_cpp_info(self):
        conanfile = ConanFile(Mock(), None)
        conanfile.initialize(Settings({}), EnvValues())
        ref = ConanFileReference.loads("MyPkg/0.1@lasote/stables")
        cpp_info = CppInfo(ref.name, "dummy_root_folder1")
        cpp_info.defines = ["MYDEFINE1"]
        cpp_info.cxxflags = ["-cxxflag_parent"]
        conanfile.deps_cpp_info.add(ref.name, cpp_info)

        ref = ConanFileReference.loads("MyPkg2/0.1@lasote/stables")
        cpp_info = CppInfo(ref.name, "dummy_root_folder2")
        cpp_info.defines = ["MYDEFINE2"]
        cpp_info.cxxflags = ["-cxxflag_dep"]
        conanfile.deps_cpp_info.add(ref.name, cpp_info)

        generator = TXTGenerator(conanfile)
        txt_out = generator.content

        self.assertIn(textwrap.dedent("""
            [cppflags_MyPkg]
            -cxxflag_parent

            [cxxflags_MyPkg]
            -cxxflag_parent"""), txt_out)

        self.assertIn(textwrap.dedent("""
            [cppflags_MyPkg]
            -cxxflag_parent

            [cxxflags_MyPkg]
            -cxxflag_parent"""), txt_out)

    def test_env_info(self):
        conanfile = ConanFile(Mock(), None)
        conanfile.initialize(Settings({}), EnvValues())

        env_info = EnvInfo()
        env_info.VAR1 = "value1"
        env_info.PATH.append("path-extended")
        conanfile.deps_env_info.update(env_info, "my_pkg")

        env_info = EnvInfo()
        env_info.VAR1 = "other-value1"
        env_info.PATH.append("other-path-extended")
        conanfile.deps_env_info.update(env_info, "other-pkg")

        generator = TXTGenerator(conanfile)
        txt_out = generator.content

        self.assertIn(textwrap.dedent("""
                    [ENV_my_pkg]
                    PATH=["path-extended"]
                    VAR1=value1
                    [ENV_other-pkg]
                    PATH=["other-path-extended"]
                    VAR1=other-value1"""), txt_out)

    def test_user_info(self):
        conanfile = ConanFile(Mock(), None)
        conanfile.initialize(Settings({}), EnvValues())

        user_info = UserInfo()
        user_info.VAR1 = "value1"
        conanfile.deps_user_info["my_pkg"] = user_info

        user_info = UserInfo()
        user_info.VAR1 = "other-value1"
        conanfile.deps_user_info["other-pkg"] = user_info

        generator = TXTGenerator(conanfile)
        txt_out = generator.content

        self.assertIn(textwrap.dedent("""
                    [USER_my_pkg]
                    VAR1=value1
                    [USER_other-pkg]
                    VAR1=other-value1"""), txt_out)

    def test_user_info_build(self):
        conanfile = ConanFile(Mock(), None)
        conanfile.initialize(Settings({}), EnvValues())

        conanfile.user_info_build = DepsUserInfo()
        user_info = UserInfo()
        user_info.VAR1 = "value1"
        conanfile.user_info_build["build_pkg"] = user_info

        user_info = UserInfo()
        user_info.VAR1 = "other-value1"
        conanfile.user_info_build["other-build-pkg"] = user_info

        generator = TXTGenerator(conanfile)
        txt_out = generator.content

        self.assertIn(textwrap.dedent("""
                    [USERBUILD_build_pkg]
                    VAR1=value1
                    [USERBUILD_other-build-pkg]
                    VAR1=other-value1"""), txt_out)
