import os
import unittest

from mock import Mock
from parameterized import parameterized

from conans.client.conf import get_default_settings_yml
from conans.client.generators import VisualStudioMultiGenerator
from conans.client.tools.files import chdir
from conans.model.build_info import CppInfo
from conans.model.conan_file import ConanFile
from conans.model.env_info import EnvValues
from conans.model.ref import ConanFileReference
from conans.model.settings import Settings
from conans.test.utils.test_files import temp_folder


class VisualStudioMultiGeneratorTest(unittest.TestCase):

    @parameterized.expand([(False, ), (True, )])
    def test_valid_xml(self, use_toolset):
        tempdir = temp_folder()
        with chdir(tempdir):
            settings = Settings.loads(get_default_settings_yml())
            settings.os = "Windows"
            settings.compiler = "Visual Studio"
            settings.compiler.version = "11"
            settings.compiler.runtime = "MD"
            if use_toolset:
                settings.compiler.toolset = "v110"
            conanfile = ConanFile(Mock(), None)
            conanfile.initialize(Settings({}), EnvValues())

            ref = ConanFileReference.loads("MyPkg/0.1@user/testing")
            cpp_info = CppInfo(ref.name, "dummy_root_folder1")
            conanfile.deps_cpp_info.add(ref.name, cpp_info)
            ref = ConanFileReference.loads("My.Fancy-Pkg_2/0.1@user/testing")
            cpp_info = CppInfo(ref.name, "dummy_root_folder2")
            conanfile.deps_cpp_info.add(ref.name, cpp_info)

            settings.arch = "x86"
            settings.build_type = "Debug"
            conanfile.settings = settings

            generator = VisualStudioMultiGenerator(conanfile)
            generator.output_path = ""
            content = generator.content

            self.assertEqual(2, len(content))
            self.assertIn('conanbuildinfo_multi.props', content.keys())
            self.assertIn('conanbuildinfo_debug_win32_v110.props', content.keys())

            content_multi = content['conanbuildinfo_multi.props']
            self.assertIn("<Import Condition=\"'$(Configuration)' == 'Debug' "
                          "And '$(Platform)' == 'Win32' "
                          "And '$(PlatformToolset)' == 'v110'\" "
                          "Project=\"conanbuildinfo_debug_win32_v110.props\"/>", content_multi)

            with open('conanbuildinfo_multi.props', 'w') as f:
                f.write(content_multi)

            settings.arch = "x86_64"
            settings.build_type = "Release"
            settings.compiler.version = "15"
            settings.compiler.toolset = "v141"
            conanfile.settings = settings

            generator = VisualStudioMultiGenerator(conanfile)
            generator.output_path = ""
            content = generator.content

            self.assertEqual(2, len(content))
            self.assertIn('conanbuildinfo_multi.props', content.keys())
            self.assertIn('conanbuildinfo_release_x64_v141.props', content.keys())

            content_multi = content['conanbuildinfo_multi.props']
            self.assertIn("<Import Condition=\"'$(Configuration)' == 'Debug' "
                          "And '$(Platform)' == 'Win32' "
                          "And '$(PlatformToolset)' == 'v110'\" "
                          "Project=\"conanbuildinfo_debug_win32_v110.props\"/>", content_multi)
            self.assertIn("<Import Condition=\"'$(Configuration)' == 'Release' "
                          "And '$(Platform)' == 'x64' "
                          "And '$(PlatformToolset)' == 'v141'\" "
                          "Project=\"conanbuildinfo_release_x64_v141.props\"/>", content_multi)

            os.unlink('conanbuildinfo_multi.props')

    def test_addional_dependencies(self):

        def validate_additional_dependencies(libname, additional_dep):
            tempdir = temp_folder()
            with chdir(tempdir):
                conanfile = ConanFile(Mock(), None)
                conanfile.initialize(Settings({}), EnvValues())

                ref = ConanFileReference.loads("MyPkg/0.1@user/testing")
                cpp_info = CppInfo(ref.name, "dummy_root_folder1")
                cpp_info.libs = [libname]
                conanfile.deps_cpp_info.add(ref.name, cpp_info)

                settings = Settings.loads(get_default_settings_yml())
                settings.os = "Windows"
                settings.arch = "x86_64"
                settings.build_type = "Release"
                settings.compiler = "Visual Studio"
                settings.compiler.version = "15"
                settings.compiler.runtime = "MD"
                settings.compiler.toolset = "v141"
                conanfile.settings = settings

                generator = VisualStudioMultiGenerator(conanfile)
                generator.output_path = ""
                content = generator.content

                self.assertIn('conanbuildinfo_release_x64_v141.props', content.keys())

                content_release = content['conanbuildinfo_release_x64_v141.props']
                self.assertIn("<ConanLibraries>%s;</ConanLibraries>" % additional_dep,
                              content_release)
                self.assertIn("<AdditionalDependencies>"
                              "$(ConanLibraries)%(AdditionalDependencies)"
                              "</AdditionalDependencies>", content_release)

        # regular
        validate_additional_dependencies("foobar", "foobar.lib")

        # .lib extension
        validate_additional_dependencies("blah.lib", "blah.lib")

        # extra dot dot
        validate_additional_dependencies("foo.v12.core", "foo.v12.core.lib")

        # extra dot dot + .lib
        validate_additional_dependencies("foo.v12.core.lib", "foo.v12.core.lib")
