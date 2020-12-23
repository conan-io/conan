import platform
import textwrap
import unittest

import pytest

from conans.test.utils.tools import TestClient


class LibcxxSettingTest(unittest.TestCase):

    @pytest.mark.skipif(platform.system() == "Windows", reason="Not in Windows")
    @pytest.mark.tool_cmake
    def test_declared_stdlib_and_passed(self):
        file_content = textwrap.dedent('''
            from conans import ConanFile, CMake

            class ConanFileToolsTest(ConanFile):
                settings = "os", "compiler", "arch", "build_type"
                generators = ["cmake"]

                def build(self):
                    cmake = CMake(self)
                    self.output.warn(cmake.command_line)
                    self.run('cmake . %s' % cmake.command_line)
                    self.run("cmake --build . %s" %  cmake.build_config)
                ''')

        cmakelists = textwrap.dedent('''PROJECT(conanzlib)
            set(CONAN_DISABLE_CHECK_COMPILER TRUE)
            cmake_minimum_required(VERSION 2.8)
            include(conanbuildinfo.cmake)
            conan_basic_setup()
            message("CXX FLAGS=> ${CMAKE_CXX_FLAGS}")
            get_directory_property( DirDefs DIRECTORY ${CMAKE_SOURCE_DIR} COMPILE_DEFINITIONS)
            foreach( d ${DirDefs} )
                message( STATUS "Found Define: " ${d} )
            endforeach()
            ''')
        client = TestClient()
        client.save({"conanfile.py": file_content,
                     "CMakeLists.txt": cmakelists})
        client.run("export . pkg/0.1@lasote/testing")

        if platform.system() == "SunOS":
            client.run('install . -s compiler=sun-cc -s compiler.libcxx=libCstd')
            client.run('build .')
            self.assertIn("-library=Cstd", client.out)

            client.run('install -s compiler=sun-cc -s compiler.libcxx=libstdcxx')
            client.run('build .')
            self.assertIn("-library=stdcxx4", client.out)

            client.run('install . -s compiler=sun-cc -s compiler.libcxx=libstlport')
            client.run('build .')
            self.assertIn("-library=stlport4", client.out)
        else:
            client.run('install . -s compiler=clang -s compiler.version=3.3 '
                       '-s compiler.libcxx=libstdc++ ')
            client.run('build .')
            self.assertIn("-stdlib=libstdc++", client.out)
            self.assertIn("Found Define: _GLIBCXX_USE_CXX11_ABI=0", client.out)

            client.run('install . -s compiler=clang -s compiler.version=3.3 '
                       '-s compiler.libcxx=libstdc++11')
            client.run('build .')
            self.assertIn("-stdlib=libstdc++", client.out)
            self.assertIn("Found Define: _GLIBCXX_USE_CXX11_ABI=1", client.out)

            client.run('install . -s compiler=clang -s compiler.version=3.3 '
                       '-s compiler.libcxx=libc++')
            client.run('build .')
            self.assertIn("-stdlib=libc++", client.out)
            self.assertNotIn("Found Define: _GLIBCXX_USE_CXX11", client.out)

    def test_C_only(self):
        conanfile = """from conans import ConanFile

class ConanFileToolsTest(ConanFile):
    name = "test"
    version = "1.9"
    settings = "os", "compiler", "arch", "build_type"

    def configure(self):
        del self.settings.compiler.libcxx # C package only
    """

        client = TestClient()
        client.save({"conanfile.py": conanfile})
        # Check that it not fails the config method with Visual Studio, because of the lack of libcxx
        client.run('install . -s compiler="Visual Studio" -s compiler.version=14')
        self.assertIn("conanfile.py (test/1.9): Generated conaninfo.txt", client.out)

        conaninfo = client.load("conaninfo.txt")
        self.assertNotIn("libcxx", conaninfo)
        client.run('install . -s compiler=gcc -s compiler.version=4.9')
        conaninfo = client.load("conaninfo.txt")
        self.assertNotIn("libcxx", conaninfo)

        client.run("create . lasote/testing -s compiler=gcc -s compiler.version=4.9")

        # Now try to reuse the installed package defining libstc++11 for the new package
        newlib_content = '''
from conans import ConanFile, CMake

class ConanFileToolsTest(ConanFile):
    settings = "os", "compiler", "arch", "build_type"
    requires = "test/1.9@lasote/testing"
    '''

        client.save({"conanfile.py": newlib_content})
        client.run('install . -s compiler=gcc -s compiler.libcxx=libstdc++11 '
                   '-s compiler.version=4.9')
        # Package is found and everything is ok
        self.assertIn("test/1.9@lasote/testing: Already installed!", client.out)
        self.assertIn("conanfile.py: Generated conaninfo.txt", client.out)
        conaninfo = client.load("conaninfo.txt")
        self.assertIn("libcxx", conaninfo)
        client.run('install . -s compiler=gcc -s compiler.libcxx=libstdc++ -s compiler.version=4.9')
        # Package is found and everything is ok
        self.assertIn("test/1.9@lasote/testing: Already installed!", client.out)
        self.assertIn("conanfile.py: Generated conaninfo.txt", client.out)
