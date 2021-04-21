import os
import textwrap
import unittest

from conans.model.graph_lock import LOCKFILE
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import (BUILD_INFO_CMAKE, BUILD_INFO_XCODE, CONANFILE_TXT)
from conans.test.utils.tools import TestClient


class VSXCodeGeneratorsTest(unittest.TestCase):

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
            cmake
            xcode
            ''')
        client.save({"conanfile.txt": conanfile_txt}, clean_first=True)

        # Install requirements
        client.run('install . --build missing')

        current_files = os.listdir(client.current_folder)
        for f in [CONANFILE_TXT, BUILD_INFO_CMAKE, BUILD_INFO_XCODE, LOCKFILE]:
            assert f in current_files

        cmake = client.load(BUILD_INFO_CMAKE)

        self.assertIn("CONAN_INCLUDE_DIRS", cmake)
        self.assertIn("CONAN_LIB_DIRS", cmake)
        self.assertIn("CONAN_LIBS", cmake)

        self.assertIn("CONAN_INCLUDE_DIRS", cmake)
        self.assertIn("CONAN_LIB_DIRS", cmake)
        self.assertIn("/data/Hello/0.1/lasote/stable/package", cmake)

        package_id = os.listdir(client.cache.package_layout(ref).packages())[0]
        pref = PackageReference(ref, package_id)
        package_path = client.cache.package_layout(pref.ref).package(pref)

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
