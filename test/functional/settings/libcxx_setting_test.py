import platform
import textwrap
import unittest

import pytest

from conan.test.utils.tools import TestClient


@pytest.mark.xfail(reason="Move this test to CMakeToolchain")
class LibcxxSettingTest(unittest.TestCase):

    @pytest.mark.skipif(platform.system() == "Windows", reason="Not in Windows")
    @pytest.mark.tool("cmake")
    def test_declared_stdlib_and_passed(self):
        file_content = textwrap.dedent('''
            from conan import ConanFile, CMake

            class ConanFileToolsTest(ConanFile):
                settings = "os", "compiler", "arch", "build_type"
                generators = ["cmake"]

                def build(self):
                    cmake = CMake(self)
                    self.output.warning(cmake.command_line)
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
        client.run("export . --name=pkg --version=0.1 --user=user --channel=testing")

        if platform.system() == "SunOS":
            client.run('build . -s compiler=sun-cc -s compiler.libcxx=libCstd')
            self.assertIn("-library=Cstd", client.out)

            client.run('build -s compiler=sun-cc -s compiler.libcxx=libstdcxx')
            self.assertIn("-library=stdcxx4", client.out)

            client.run('build . -s compiler=sun-cc -s compiler.libcxx=libstlport')
            self.assertIn("-library=stlport4", client.out)
        else:
            client.run('build . -s compiler=clang -s compiler.version=3.3 '
                       '-s compiler.libcxx=libstdc++ ')
            self.assertIn("-stdlib=libstdc++", client.out)
            self.assertIn("Found Define: _GLIBCXX_USE_CXX11_ABI=0", client.out)

            client.run('build . -s compiler=clang -s compiler.version=3.3 '
                       '-s compiler.libcxx=libstdc++11')
            self.assertIn("-stdlib=libstdc++", client.out)
            self.assertIn("Found Define: _GLIBCXX_USE_CXX11_ABI=1", client.out)

            client.run('build . -s compiler=clang -s compiler.version=3.3 '
                       '-s compiler.libcxx=libc++')
            self.assertIn("-stdlib=libc++", client.out)
            self.assertNotIn("Found Define: _GLIBCXX_USE_CXX11", client.out)
