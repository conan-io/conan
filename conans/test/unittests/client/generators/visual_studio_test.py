import os
import unittest
import xml.etree.ElementTree

from mock import Mock

from conans.client import tools
from conans.client.generators import VisualStudioGenerator
from conans.model.build_info import CppInfo
from conans.model.conan_file import ConanFile
from conans.model.env_info import EnvValues
from conans.model.ref import ConanFileReference
from conans.model.settings import Settings
from conans.test.utils.test_files import temp_folder
from conans.util.files import save


class VisualStudioGeneratorTest(unittest.TestCase):

    def test_valid_xml(self):
        conanfile = ConanFile(Mock(), None)
        conanfile.initialize(Settings({}), EnvValues())
        ref = ConanFileReference.loads("MyPkg/0.1@user/testing")
        cpp_info = CppInfo(ref.name, "dummy_root_folder1")
        conanfile.deps_cpp_info.add(ref.name, cpp_info)
        ref = ConanFileReference.loads("My.Fancy-Pkg_2/0.1@user/testing")
        cpp_info = CppInfo(ref.name, "dummy_root_folder2")
        conanfile.deps_cpp_info.add(ref.name, cpp_info)
        generator = VisualStudioGenerator(conanfile)

        content = generator.content
        xml.etree.ElementTree.fromstring(content)

        self.assertIn('<PropertyGroup Label="Conan-RootDirs">', content)
        self.assertIn("<Conan-MyPkg-Root>dummy_root_folder1</Conan-MyPkg-Root>", content)
        self.assertIn("<Conan-My-Fancy-Pkg_2-Root>dummy_root_folder2</Conan-My-Fancy-Pkg_2-Root>",
                      content)

    def test_user_profile(self):
        conanfile = ConanFile(Mock(), None)
        conanfile.initialize(Settings({}), EnvValues())
        ref = ConanFileReference.loads("MyPkg/0.1@user/testing")
        tmp_folder = temp_folder()
        pkg1 = os.path.join(tmp_folder, "pkg1")
        cpp_info = CppInfo(ref.name, pkg1)
        cpp_info.includedirs = ["include"]
        save(os.path.join(pkg1, "include", "file.h"), "")
        conanfile.deps_cpp_info.add(ref.name, cpp_info)
        ref = ConanFileReference.loads("My.Fancy-Pkg_2/0.1@user/testing")
        pkg2 = os.path.join(tmp_folder, "pkg2")
        cpp_info = CppInfo(ref.name, pkg2)
        cpp_info.includedirs = ["include"]
        save(os.path.join(pkg2, "include", "file.h"), "")
        conanfile.deps_cpp_info.add(ref.name, cpp_info)
        generator = VisualStudioGenerator(conanfile)

        path1 = os.path.join("$(USERPROFILE)", "pkg1", "include")
        path2 = os.path.join("$(USERPROFILE)", "pkg2", "include")
        expected1 = "<ConanIncludeDirectories>%s;%s;" % (path1, path2)
        expected2 = "<AdditionalIncludeDirectories>$(ConanIncludeDirectories)%(AdditionalIncludeDirectories)</AdditionalIncludeDirectories>"

        with tools.environment_append({"USERPROFILE": tmp_folder}):
            content = generator.content
            xml.etree.ElementTree.fromstring(content)
            self.assertIn(expected1, content)
            self.assertIn(expected2, content)

        with tools.environment_append({"USERPROFILE": tmp_folder.upper()}):
            content = generator.content
            xml.etree.ElementTree.fromstring(content)
            self.assertIn(expected1, content)
            self.assertIn(expected2, content)

    def test_multi_config(self):
        tmp_folder = temp_folder()
        ref = ConanFileReference.loads("MyPkg/0.1@lasote/stables")
        conanfile = ConanFile(Mock(), None)
        conanfile.initialize(Settings({}), EnvValues())
        cpp_info = CppInfo(ref.name, tmp_folder)
        cpp_info.defines = ["_WIN32_WINNT=x0501"]
        cpp_info.debug.defines = ["_DEBUG", "DEBUG"]
        cpp_info.release.defines = ["NDEBUG"]
        cpp_info.custom.defines = ["CUSTOM_BUILD"]
        conanfile.deps_cpp_info.add(ref.name, cpp_info)
        generator = VisualStudioGenerator(conanfile)

        content = generator.content

        defines_common = "<ConanPreprocessorDefinitions>" \
                         "_WIN32_WINNT=x0501;" \
                         "</ConanPreprocessorDefinitions>"
        defines_debug = "<ConanPreprocessorDefinitions>" \
                        "_DEBUG;DEBUG;" \
                        "</ConanPreprocessorDefinitions>"
        defines_release = "<ConanPreprocessorDefinitions>" \
                          "NDEBUG;" \
                          "</ConanPreprocessorDefinitions>"
        defines_custom = "<ConanPreprocessorDefinitions>" \
                         "CUSTOM_BUILD;" \
                         "</ConanPreprocessorDefinitions>"
        defines_always = "<PreprocessorDefinitions>$(ConanPreprocessorDefinitions)%(PreprocessorDefinitions)</PreprocessorDefinitions>"

        self.assertIn(defines_common, content)
        self.assertIn(defines_debug, content)
        self.assertIn(defines_release, content)
        self.assertIn(defines_custom, content)
        self.assertIn(defines_always, content)

        condition_debug = "<ItemDefinitionGroup Condition=\"'$(Configuration)' == 'debug'\">"
        condition_release = "<ItemDefinitionGroup Condition=\"'$(Configuration)' == 'release'\">"
        condition_custom = "<ItemDefinitionGroup Condition=\"'$(Configuration)' == 'custom'\">"
        self.assertIn(condition_debug, content)
        self.assertIn(condition_release, content)
        self.assertIn(condition_custom, content)

    def test_addional_dependencies(self):

        def validate_additional_dependencies(lib, additional_dep):
            conanfile = ConanFile(Mock(), None)
            conanfile.initialize(Settings({}), EnvValues())
            ref = ConanFileReference.loads("MyPkg/0.1@user/testing")
            cpp_info = CppInfo(ref.name, "dummy_root_folder1")
            cpp_info.libs = [lib]
            conanfile.deps_cpp_info.add(ref.name, cpp_info)
            generator = VisualStudioGenerator(conanfile)
            content = generator.content
            self.assertIn("<ConanLibraries>%s;</ConanLibraries>" % additional_dep, content)
            self.assertIn("<AdditionalDependencies>"
                          "$(ConanLibraries)%(AdditionalDependencies)"
                          "</AdditionalDependencies>", content)

        # regular
        validate_additional_dependencies("foobar", "foobar.lib")

        # .lib extension
        validate_additional_dependencies("blah.lib", "blah.lib")

        # extra dot dot
        validate_additional_dependencies("foo.v12.core", "foo.v12.core.lib")

        # extra dot dot + .lib
        validate_additional_dependencies("foo.v12.core.lib", "foo.v12.core.lib")

        # extra case libiconv
        validate_additional_dependencies("libiconv.dll.lib", "libiconv.dll.lib")

        # extra case ffmpeg
        validate_additional_dependencies("libavcodec.a", "libavcodec.a")
