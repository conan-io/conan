import unittest
from conans.model.ref import ConanFileReference, PackageReference

from conans.paths import (CONANFILE_TXT, BUILD_INFO_CMAKE, BUILD_INFO_GCC, CONANINFO,
                          BUILD_INFO_VISUAL_STUDIO, BUILD_INFO_XCODE, BUILD_INFO)
from conans.util.files import load
import os
from conans.test.utils.tools import TestClient
import re


class VSXCodeGeneratorsTest(unittest.TestCase):

    def generators_test(self):
        conan_ref = ConanFileReference.loads("Hello/0.1@lasote/stable")
        client = TestClient()
        client.save({"conanfile.py": """from conans import ConanFile
import os
class Pkg(ConanFile):
    def package(self):
        os.makedirs(os.path.join(self.package_folder, "lib"))
        os.makedirs(os.path.join(self.package_folder, "include"))
    def package_info(self):
        self.cpp_info.libs = ["hello"]
        self.cpp_info.cppflags = ["-some_cpp_compiler_flag"]
        self.cpp_info.cflags = ["-some_c_compiler_flag"]
"""})
        client.run("export . Hello/0.1@lasote/stable")
        conanfile_txt = '''[requires]
Hello/0.1@lasote/stable # My req comment
[generators]
gcc # I need this generator for..
cmake
visual_studio
xcode
'''
        client.save({"conanfile.txt": conanfile_txt}, clean_first=True)

        # Install requirements
        client.run('install . --build missing')
        self.assertEqual(sorted([CONANFILE_TXT, BUILD_INFO_GCC, BUILD_INFO_CMAKE,
                                 BUILD_INFO_VISUAL_STUDIO, BUILD_INFO,
                                 BUILD_INFO_XCODE, CONANINFO]),
                         sorted(os.listdir(client.current_folder)))

        cmake = load(os.path.join(client.current_folder, BUILD_INFO_CMAKE))
        gcc = load(os.path.join(client.current_folder, BUILD_INFO_GCC))

        self.assertIn("CONAN_INCLUDE_DIRS", cmake)
        self.assertIn("CONAN_LIB_DIRS", cmake)
        self.assertIn("CONAN_LIBS", cmake)

        self.assertIn("CONAN_INCLUDE_DIRS", cmake)
        self.assertIn("CONAN_LIB_DIRS", cmake)
        self.assertIn(".conan/data/Hello/0.1/lasote/stable/package", cmake)

        self.assertIn("-L", gcc)
        self.assertIn("-l", gcc)
        self.assertIn("-I", gcc)

        self.assertIn(".conan/data/Hello/0.1/lasote/stable/package", gcc)

        # CHECK VISUAL STUDIO GENERATOR

        from xml.dom import minidom
        xmldoc = minidom.parse(os.path.join(client.current_folder, BUILD_INFO_VISUAL_STUDIO))
        definition_group = xmldoc.getElementsByTagName('ItemDefinitionGroup')[0]
        compiler = definition_group.getElementsByTagName("ClCompile")[0]

        include_dirs = compiler.getElementsByTagName("AdditionalIncludeDirectories")[0].firstChild.data
        definitions = compiler.getElementsByTagName("PreprocessorDefinitions")[0].firstChild.data

        linker = definition_group.getElementsByTagName("Link")[0]
        lib_dirs = linker.getElementsByTagName("AdditionalLibraryDirectories")[0].firstChild.data
        libs = linker.getElementsByTagName("AdditionalDependencies")[0].firstChild.data

        package_id = os.listdir(client.paths.packages(conan_ref))[0]
        package_ref = PackageReference(conan_ref, package_id)
        package_path = client.paths.package(package_ref).replace("\\", "/")

        replaced_path = re.sub(os.getenv("USERPROFILE", "not user profile").replace("\\", "/"),
                               "$(USERPROFILE)", package_path, flags=re.I)
        expected_lib_dirs = os.path.join(replaced_path, "lib").replace("\\", "/")
        expected_include_dirs = os.path.join(replaced_path, "include").replace("\\", "/")

        self.assertIn(expected_lib_dirs, lib_dirs)
        self.assertEquals("hello.lib;%(AdditionalDependencies)", libs)
        self.assertEquals("%(PreprocessorDefinitions)", definitions)
        self.assertIn(expected_include_dirs, include_dirs)

        # CHECK XCODE GENERATOR
        xcode = load(os.path.join(client.current_folder, BUILD_INFO_XCODE))

        expected_c_flags = '-some_c_compiler_flag'
        expected_cpp_flags = '-some_cpp_compiler_flag'
        expected_lib_dirs = os.path.join(package_path, "lib").replace("\\", "/")
        expected_include_dirs = os.path.join(package_path, "include").replace("\\", "/")

        self.assertIn('LIBRARY_SEARCH_PATHS = $(inherited) "%s"' % expected_lib_dirs, xcode)
        self.assertIn('HEADER_SEARCH_PATHS = $(inherited) "%s"' % expected_include_dirs, xcode)
        self.assertIn("GCC_PREPROCESSOR_DEFINITIONS = $(inherited)", xcode)
        self.assertIn('OTHER_CFLAGS = $(inherited) %s' % expected_c_flags, xcode)
        self.assertIn('OTHER_CPLUSPLUSFLAGS = $(inherited) %s' % expected_cpp_flags, xcode)
        self.assertIn('FRAMEWORK_SEARCH_PATHS = $(inherited) "%s"' % package_path.replace("\\", "/"), xcode)
