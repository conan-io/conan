import os
import re
import textwrap
import unittest

from conans.model.graph_info import GRAPH_INFO_FILE
from conans.model.graph_lock import LOCKFILE
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import (BUILD_INFO, BUILD_INFO_CMAKE, BUILD_INFO_GCC, BUILD_INFO_VISUAL_STUDIO,
                          BUILD_INFO_XCODE, CONANFILE_TXT, CONANINFO)
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


class VSXCodeGeneratorsTest(unittest.TestCase):

    def test_frameworks_no_compiler(self):
        client = TestClient()
        client.save({"conanfile.py": textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                def package_info(self):
                    self.cpp_info.frameworks = ["CoreAudio"]
            """)})
        client.run("export . Hello/0.1@lasote/stable")

        client.save({"conanfile.py": GenConanfile().with_requires("Hello/0.1@lasote/stable").with_generator("xcode")})
        client.run('install . --build missing')
        xcode = client.load(BUILD_INFO_XCODE)
        self.assertIn('OTHER_LDFLAGS = $(inherited)    -framework CoreAudio', xcode)

    def test_generators(self):
        ref = ConanFileReference.loads("Hello/0.1@lasote/stable")
        client = TestClient()
        client.save({"conanfile.py": textwrap.dedent("""
            from conans import ConanFile
            import os
            class Pkg(ConanFile):
                def package(self):
                    os.makedirs(os.path.join(self.package_folder, "lib"))
                    os.makedirs(os.path.join(self.package_folder, "include"))
                def package_info(self):
                    self.cpp_info.libs = ["hello"]
                    self.cpp_info.cxxflags = ["-some_cxx_compiler_flag"]
                    self.cpp_info.cflags = ["-some_c_compiler_flag"]
                    self.cpp_info.system_libs = ["system_lib1"]
            """)})
        client.run("export . Hello/0.1@lasote/stable")
        conanfile_txt = textwrap.dedent('''
            [requires]
            Hello/0.1@lasote/stable # My req comment
            [generators]
            gcc # I need this generator for..
            cmake
            visual_studio
            xcode
            ''')
        client.save({"conanfile.txt": conanfile_txt}, clean_first=True)

        # Install requirements
        client.run('install . --build missing')
        current_files = os.listdir(client.current_folder)
        for f in [CONANFILE_TXT, BUILD_INFO_GCC, BUILD_INFO_CMAKE, BUILD_INFO_VISUAL_STUDIO,
                  BUILD_INFO, BUILD_INFO_XCODE, CONANINFO, GRAPH_INFO_FILE, LOCKFILE]:
            assert f in current_files

        cmake = client.load(BUILD_INFO_CMAKE)
        gcc = client.load(BUILD_INFO_GCC)

        self.assertIn("CONAN_INCLUDE_DIRS", cmake)
        self.assertIn("CONAN_LIB_DIRS", cmake)
        self.assertIn("CONAN_LIBS", cmake)

        self.assertIn("CONAN_INCLUDE_DIRS", cmake)
        self.assertIn("CONAN_LIB_DIRS", cmake)
        self.assertIn("/data/Hello/0.1/lasote/stable/package", cmake)

        self.assertIn("-L", gcc)
        self.assertIn("-l", gcc)
        self.assertIn("-I", gcc)

        self.assertIn("/data/Hello/0.1/lasote/stable/package", gcc)

        # CHECK VISUAL STUDIO GENERATOR

        from xml.dom import minidom
        xmldoc = minidom.parse(os.path.join(client.current_folder, BUILD_INFO_VISUAL_STUDIO))
        definition_group = xmldoc.getElementsByTagName('ItemDefinitionGroup')[0]
        _ = definition_group.getElementsByTagName("ClCompile")[0]
        linker = definition_group.getElementsByTagName("Link")[0]

        def element_content(node):
            return node.firstChild.data if node.firstChild else ""

        include_dirs = element_content(xmldoc.getElementsByTagName("ConanIncludeDirectories")[0])
        definitions = element_content(xmldoc.getElementsByTagName("ConanPreprocessorDefinitions")[0])
        lib_dirs = element_content(xmldoc.getElementsByTagName("ConanLibraryDirectories")[0])
        libs = element_content(linker.getElementsByTagName("AdditionalDependencies")[0])
        system_libs = element_content(linker.getElementsByTagName("AdditionalDependencies")[1])

        package_id = os.listdir(client.cache.package_layout(ref).packages())[0]
        pref = PackageReference(ref, package_id)
        package_path = client.cache.package_layout(pref.ref).package(pref)

        replaced_path = re.sub(os.getenv("USERPROFILE", "not user profile").replace("\\", "\\\\"),
                               "$(USERPROFILE)", package_path, flags=re.I)
        expected_lib_dirs = os.path.join(replaced_path, "lib")
        expected_include_dirs = os.path.join(replaced_path, "include")

        self.assertIn(expected_lib_dirs, lib_dirs)
        self.assertEqual("$(ConanLibraries)%(AdditionalDependencies)", libs)
        self.assertEqual("$(ConanSystemDeps)%(AdditionalDependencies)", system_libs)
        self.assertEqual("", definitions)
        self.assertIn(expected_include_dirs, include_dirs)

        # CHECK XCODE GENERATOR
        xcode = client.load(BUILD_INFO_XCODE)

        expected_c_flags = '-some_c_compiler_flag'
        expected_cpp_flags = '-some_cxx_compiler_flag'
        expected_lib_dirs = os.path.join(package_path, "lib").replace("\\", "/")
        expected_include_dirs = os.path.join(package_path, "include").replace("\\", "/")

        self.assertIn('LIBRARY_SEARCH_PATHS = $(inherited) "%s"' % expected_lib_dirs, xcode)
        self.assertIn('HEADER_SEARCH_PATHS = $(inherited) "%s"' % expected_include_dirs, xcode)
        self.assertIn("GCC_PREPROCESSOR_DEFINITIONS = $(inherited)", xcode)
        self.assertIn('OTHER_CFLAGS = $(inherited) %s' % expected_c_flags, xcode)
        self.assertIn('OTHER_CPLUSPLUSFLAGS = $(inherited) %s' % expected_cpp_flags, xcode)
        self.assertIn('FRAMEWORK_SEARCH_PATHS = $(inherited) "%s"' % package_path.replace("\\", "/"),
                      xcode)
        self.assertIn('OTHER_LDFLAGS = $(inherited)  -lhello -lsystem_lib1',
                      xcode)
