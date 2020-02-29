# coding=utf-8
import textwrap
import unittest

from conans.client.generators.text import TXTGenerator
from conans.model.build_info import CppInfo
from conans.model.conan_file import ConanFile
from conans.model.env_info import EnvValues
from conans.model.ref import ConanFileReference
from conans.model.settings import Settings
from conans.test.utils.tools import TestBufferConanOutput


class TextGeneratorTest(unittest.TestCase):

    def test_content(self):
        conanfile = ConanFile(TestBufferConanOutput(), None)
        conanfile.initialize(Settings({}), EnvValues())
        ref = ConanFileReference.loads("MyPkg/0.1@lasote/stables")
        cpp_info = CppInfo("dummy_root_folder1")
        cpp_info.defines = ["MYDEFINE1"]
        cpp_info.cxxflags = ["-cxxflag_parent"]

        conanfile.deps_cpp_info.update(cpp_info, ref.name)
        ref = ConanFileReference.loads("MyPkg2/0.1@lasote/stables")
        cpp_info = CppInfo("dummy_root_folder2")
        cpp_info.defines = ["MYDEFINE2"]
        cpp_info.cxxflags = ["-cxxflag_dep"]
        conanfile.deps_cpp_info.update(cpp_info, ref.name)

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
