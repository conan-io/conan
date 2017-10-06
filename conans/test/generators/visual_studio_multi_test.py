#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import os
from nose.plugins.attrib import attr
from conans.model.settings import Settings
from conans.model.conan_file import ConanFile
from conans.model.build_info import CppInfo
from conans.model.ref import ConanFileReference
from conans.client.conf import default_settings_yml

from conans.client.generators import VisualStudioMultiGenerator
from conans.tools import chdir
from conans.test.utils.test_files import temp_folder


@attr('visual_studio')
class VisualStudioMultiGeneratorTest(unittest.TestCase):
    def valid_xml_test(self):

        tempdir = temp_folder()
        with chdir(tempdir):
            settings = Settings.loads(default_settings_yml)
            settings.os = "Windows"
            settings.compiler = "Visual Studio"
            settings.compiler.version = "12"
            settings.compiler.runtime = "MD"
            conanfile = ConanFile(None, None, Settings({}), None)

            ref = ConanFileReference.loads("MyPkg/0.1@user/testing")
            cpp_info = CppInfo("dummy_root_folder1")
            conanfile.deps_cpp_info.update(cpp_info, ref.name)
            ref = ConanFileReference.loads("My.Fancy-Pkg_2/0.1@user/testing")
            cpp_info = CppInfo("dummy_root_folder2")
            conanfile.deps_cpp_info.update(cpp_info, ref.name)

            settings.arch = "x86"
            settings.build_type = "Debug"
            settings.compiler.version = "12"
            conanfile.settings = settings

            generator = VisualStudioMultiGenerator(conanfile)
            generator.output_path = ""
            content = generator.content

            self.assertEqual(2, len(content))
            self.assertIn('conanbuildinfo_multi.props', content.keys())
            self.assertIn('conanbuildinfo_debug_win32_12.props', content.keys())

            content_multi = content['conanbuildinfo_multi.props']
            self.assertIn("<Import Condition=\" '$(Configuration)' == 'Debug' "
                          "And '$(Platform)' == 'Win32' "
                          "And '$(VisualStudioVersion)' == '12.0' \" "
                          "Project=\"conanbuildinfo_debug_win32_12.props\"/>", content_multi)

            with open('conanbuildinfo_multi.props', 'w') as f:
                f.write(content_multi)

            settings.arch = "x86_64"
            settings.build_type = "Release"
            settings.compiler.version = "14"
            conanfile.settings = settings

            generator = VisualStudioMultiGenerator(conanfile)
            generator.output_path = ""
            content = generator.content

            self.assertEqual(2, len(content))
            self.assertIn('conanbuildinfo_multi.props', content.keys())
            self.assertIn('conanbuildinfo_release_x64_14.props', content.keys())

            content_multi = content['conanbuildinfo_multi.props']
            self.assertIn("<Import Condition=\" '$(Configuration)' == 'Debug' "
                          "And '$(Platform)' == 'Win32' "
                          "And '$(VisualStudioVersion)' == '12.0' \" "
                          "Project=\"conanbuildinfo_debug_win32_12.props\"/>", content_multi)
            self.assertIn("<Import Condition=\" '$(Configuration)' == 'Release' "
                          "And '$(Platform)' == 'x64' "
                          "And '$(VisualStudioVersion)' == '14.0' \" "
                          "Project=\"conanbuildinfo_release_x64_14.props\"/>", content_multi)

            os.unlink('conanbuildinfo_multi.props')
