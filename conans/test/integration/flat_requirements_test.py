import unittest
from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.paths import (CONANFILE_TXT, BUILD_INFO_CMAKE, BUILD_INFO_GCC, CONANINFO,
                          BUILD_INFO_VISUAL_STUDIO, BUILD_INFO_XCODE)
from conans.util.files import save, load
import os
from conans.test.utils.tools import TestClient
from conans.test.utils.test_files import temp_folder


class FlatRequirementsTest(unittest.TestCase):

    def setUp(self):
        self.conan_reference = ConanFileReference.loads("Hello0/0.1@lasote/stable")
        self.files = cpp_hello_conan_files("Hello0", "0.1", build=False)
        self.conan = TestClient()
        self.conan.save(self.files)
        self.conan.run("export lasote/stable")

    def consumer_with_flat_requirement_test(self):
        # We want to reuse exported Hello0/0.1@lasote/stable
        tmp_dir = temp_folder()
        req_file = '''[requires]
Hello0/0.1@lasote/stable # My req comment
[generators]
gcc # I need this generator for..
cmake
visual_studio
xcode
'''
        save(os.path.join(tmp_dir, CONANFILE_TXT), req_file)

        self.conan.current_folder = tmp_dir
        # Install requirements
        self.conan.run('install --build missing')
        self.assertEqual(sorted([CONANFILE_TXT, BUILD_INFO_GCC, BUILD_INFO_CMAKE,
                                 BUILD_INFO_VISUAL_STUDIO, BUILD_INFO_XCODE, CONANINFO]),
                         sorted(os.listdir(tmp_dir)))

        cmake = load(os.path.join(tmp_dir, BUILD_INFO_CMAKE))
        gcc = load(os.path.join(tmp_dir, BUILD_INFO_GCC))

        self.assertIn("CONAN_INCLUDE_DIRS", cmake)
        self.assertIn("CONAN_LIB_DIRS", cmake)
        self.assertIn("CONAN_LIBS", cmake)

        self.assertIn("CONAN_INCLUDE_DIRS", cmake)
        self.assertIn("CONAN_LIB_DIRS", cmake)
        self.assertIn(".conan/data/Hello0/0.1/lasote/stable/package", cmake)

        self.assertIn("-L", gcc)
        self.assertIn("-l", gcc)
        self.assertIn("-I", gcc)

        self.assertIn(".conan/data/Hello0/0.1/lasote/stable/package", gcc)

        # CHECK VISUAL STUDIO GENERATOR

        from xml.dom import minidom
        xmldoc = minidom.parse(os.path.join(tmp_dir, BUILD_INFO_VISUAL_STUDIO))
        definition_group = xmldoc.getElementsByTagName('ItemDefinitionGroup')[0]
        compiler = definition_group.getElementsByTagName("ClCompile")[0]

        include_dirs = compiler.getElementsByTagName("AdditionalIncludeDirectories")[0].firstChild.data
        definitions = compiler.getElementsByTagName("PreprocessorDefinitions")[0].firstChild.data

        linker = definition_group.getElementsByTagName("Link")[0]
        lib_dirs = linker.getElementsByTagName("AdditionalLibraryDirectories")[0].firstChild.data
        libs = linker.getElementsByTagName("AdditionalDependencies")[0].firstChild.data

        package_id = os.listdir(self.conan.paths.packages(self.conan_reference))[0]
        package_ref = PackageReference(self.conan_reference, package_id)
        package_paths = self.conan.paths.package(package_ref).replace("\\", "/")

        expected_lib_dirs = os.path.join(package_paths, "lib").replace("\\", "/")
        expected_include_dirs = os.path.join(package_paths, "include").replace("\\", "/")

        self.assertIn(expected_lib_dirs, lib_dirs)
        self.assertEquals("helloHello0.lib;%(AdditionalDependencies)", libs)
        self.assertEquals("%(PreprocessorDefinitions)", definitions)
        self.assertIn(expected_include_dirs, include_dirs)

        # CHECK XCODE GENERATOR
        xcode = load(os.path.join(tmp_dir, BUILD_INFO_XCODE))

        self.assertIn('LIBRARY_SEARCH_PATHS = $(inherited) "%s"' % expected_lib_dirs, xcode)
        self.assertIn('HEADER_SEARCH_PATHS = $(inherited) "%s"' % expected_include_dirs, xcode)
        self.assertIn("GCC_PREPROCESSOR_DEFINITIONS = $(inherited)", xcode)
        self.assertIn("OTHER_CFLAGS = $(inherited)", xcode)
        self.assertIn("OTHER_CPLUSPLUSFLAGS = $(inherited)", xcode)
