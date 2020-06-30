import textwrap
import unittest

from conans.client.generators.text import TXTGenerator
from conans.model.build_info import CppInfo, DepCppInfo
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

    def test_load_sytem_libs(self):
        content = textwrap.dedent("""
            [system_libs]
            a-real-flow-contains-aggregated-list-here

            [name_requirement]
            requirement_name

            [rootpath_requirement]
            requirement_rootpath

            [system_libs_requirement]
            requirement

            [name_requirement_other]
            requirement_other_name

            [rootpath_requirement_other]
            requirement_other_rootpath

            [system_libs_requirement_other]
            requirement_other
        """)

        deps_cpp_info, _, _ = TXTGenerator.loads(content)
        self.assertListEqual(list(deps_cpp_info.system_libs), ["requirement", "requirement_other"])
        self.assertListEqual(list(deps_cpp_info["requirement"].system_libs), ["requirement", ])
        self.assertListEqual(list(deps_cpp_info["requirement_other"].system_libs),
                             ["requirement_other", ])

    def test_names_per_generator(self):
        cpp_info = CppInfo("pkg_name", "root")
        cpp_info.name = "name"
        cpp_info.names["txt"] = "txt_name"
        cpp_info.names["cmake_find_package"] = "cmake_find_package"
        conanfile = ConanFile(TestBufferConanOutput(), None)
        conanfile.initialize(Settings({}), EnvValues())
        conanfile.deps_cpp_info.add("pkg_name", DepCppInfo(cpp_info))
        content = TXTGenerator(conanfile).content
        parsed_deps_cpp_info, _, _ = TXTGenerator.loads(content, filter_empty=False)

        parsed_cpp_info = parsed_deps_cpp_info["pkg_name"]
        # FIXME: Conan v2: Remove 'txt' generator or serialize all the names
        self.assertEqual(parsed_cpp_info.get_name("txt"), "txt_name")
        self.assertEqual(parsed_cpp_info.get_name("cmake_find_package"), "pkg_name")
        self.assertEqual(parsed_cpp_info.get_name("pkg_config"), "pkg_name")

    def test_read_write(self):
        conanfile = ConanFile(TestBufferConanOutput(), None)
        conanfile.initialize(Settings({}), EnvValues())
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

        master_content = TXTGenerator(conanfile).content
        after_parse, _, _ = TXTGenerator.loads(master_content, filter_empty=False)
        conanfile.deps_cpp_info = after_parse
        after_content = TXTGenerator(conanfile).content

        self.assertListEqual(master_content.splitlines(), after_content.splitlines())
