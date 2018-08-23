import unittest
import xml.etree.ElementTree

from conans.client.generators import VisualStudioGenerator

from conans.model.settings import Settings
from conans.model.conan_file import ConanFile
from conans.model.build_info import CppInfo
from conans.model.ref import ConanFileReference
from conans.test.utils.test_files import temp_folder
from conans.util.files import save
import os
from conans import tools
from conans.model.env_info import EnvValues


class VisualStudioGeneratorTest(unittest.TestCase):

    def valid_xml_test(self):
        conanfile = ConanFile(None, None)
        conanfile.initialize(Settings({}), EnvValues())
        ref = ConanFileReference.loads("MyPkg/0.1@user/testing")
        cpp_info = CppInfo("dummy_root_folder1")
        conanfile.deps_cpp_info.update(cpp_info, ref.name)
        ref = ConanFileReference.loads("My.Fancy-Pkg_2/0.1@user/testing")
        cpp_info = CppInfo("dummy_root_folder2")
        conanfile.deps_cpp_info.update(cpp_info, ref.name)
        generator = VisualStudioGenerator(conanfile)

        content = generator.content
        xml.etree.ElementTree.fromstring(content)

        self.assertIn('<PropertyGroup Label="Conan-RootDirs">', content)
        self.assertIn("<Conan-MyPkg-Root>dummy_root_folder1</Conan-MyPkg-Root>", content)
        self.assertIn("<Conan-My-Fancy-Pkg_2-Root>dummy_root_folder2</Conan-My-Fancy-Pkg_2-Root>", content)

    def user_profile_test(self):
        conanfile = ConanFile(None, None)
        conanfile.initialize(Settings({}), EnvValues())
        ref = ConanFileReference.loads("MyPkg/0.1@user/testing")
        tmp_folder = temp_folder()
        pkg1 = os.path.join(tmp_folder, "pkg1")
        cpp_info = CppInfo(pkg1)
        cpp_info.includedirs = ["include"]
        save(os.path.join(pkg1, "include/file.h"), "")
        conanfile.deps_cpp_info.update(cpp_info, ref.name)
        ref = ConanFileReference.loads("My.Fancy-Pkg_2/0.1@user/testing")
        pkg2 = os.path.join(tmp_folder, "pkg2")
        cpp_info = CppInfo(pkg2)
        cpp_info.includedirs = ["include"]
        save(os.path.join(pkg2, "include/file.h"), "")
        conanfile.deps_cpp_info.update(cpp_info, ref.name)
        generator = VisualStudioGenerator(conanfile)

        with tools.environment_append({"USERPROFILE": tmp_folder}):
            content = generator.content
            xml.etree.ElementTree.fromstring(content)
            self.assertIn("<AdditionalIncludeDirectories>$(USERPROFILE)/pkg1/include;"
                          "$(USERPROFILE)/pkg2/include;", content)

        with tools.environment_append({"USERPROFILE": tmp_folder.upper()}):
            content = generator.content
            xml.etree.ElementTree.fromstring(content)
            self.assertIn("<AdditionalIncludeDirectories>$(USERPROFILE)/pkg1/include;"
                          "$(USERPROFILE)/pkg2/include;", content)
