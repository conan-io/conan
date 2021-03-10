import platform
import unittest

import pytest
from mock import Mock

from conans.client.generators.text import TXTGenerator
from conans.model.build_info import CppInfo
from conans.model.conan_file import ConanFile
from conans.model.env_info import EnvValues
from conans.model.ref import ConanFileReference
from conans.model.settings import Settings


class AbsPathsTestCase(unittest.TestCase):

    @pytest.mark.skipif(platform.system() == "Windows", reason="Uses unix-like paths")
    def test_abs_path_unix(self):
        conanfile = ConanFile(Mock(), None)
        conanfile.initialize(Settings({}), EnvValues())
        ref = ConanFileReference.loads("pkg/0.1")
        cpp_info = CppInfo(ref.name, "/rootdir")
        cpp_info.includedirs = ["/an/absolute/dir"]
        cpp_info.filter_empty = False
        conanfile.deps_cpp_info.add(ref.name, cpp_info)

        master_content = TXTGenerator(conanfile).content
        after_cpp_info, _, _, _ = TXTGenerator.loads(master_content, filter_empty=False)
        self.assertListEqual(after_cpp_info[ref.name].includedirs, ["../an/absolute/dir"])
        self.assertListEqual(after_cpp_info[ref.name].include_paths, ["/rootdir/../an/absolute/dir"])

    @pytest.mark.skipif(platform.system() != "Windows", reason="Uses windows-like paths")
    def test_absolute_directory(self):
        conanfile = ConanFile(Mock(), None)
        conanfile.initialize(Settings({}), EnvValues())
        ref = ConanFileReference.loads("pkg/0.1")
        cpp_info = CppInfo(ref.name, "C:/my/root/path")
        cpp_info.includedirs = ["D:/my/path/to/something"]
        cpp_info.filter_empty = False
        conanfile.deps_cpp_info.add(ref.name, cpp_info)

        master_content = TXTGenerator(conanfile).content
        after_cpp_info, _, _, _ = TXTGenerator.loads(master_content, filter_empty=False)
        self.assertListEqual(after_cpp_info[ref.name].includedirs, ["D:/my/path/to/something"])
        self.assertListEqual(after_cpp_info[ref.name].include_paths, ["D:/my/path/to/something"])
