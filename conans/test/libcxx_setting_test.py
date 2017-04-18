import unittest
from conans.test.utils.tools import TestClient
import platform
from conans.util.files import load
import os


file_content = '''
from conans import ConanFile, CMake

class ConanFileToolsTest(ConanFile):
    name = "test"
    version = "1.9"
    settings = "os", "compiler", "arch", "build_type"
    url = "1"
    license = "2"
    export = ["CMakeLists.txt", "main.c"]
    generators = ["cmake"]

    def build(self):
        self.output.warn("Building...")
        cmake = CMake(self)
        self.output.warn(cmake.command_line)
        command = cmake.command_line.replace('-G "Visual Studio 12 Win64"', "")
        self.run('cmake . %s' % command)
        self.run("cmake --build . %s" %  cmake.build_config)

    def package(self):
        self.copy("*", ".", ".")

    '''
cmakelists = '''PROJECT(conanzlib)
set(CONAN_DISABLE_CHECK_COMPILER TRUE)
cmake_minimum_required(VERSION 2.8)
include(conanbuildinfo.cmake)
CONAN_BASIC_SETUP()
MESSAGE("CXX FLAGS=> ${CMAKE_CXX_FLAGS}")
get_directory_property( DirDefs DIRECTORY ${CMAKE_SOURCE_DIR} COMPILE_DEFINITIONS)
foreach( d ${DirDefs} )
    message( STATUS "Found Define: " ${d} )
endforeach()
'''


def nowintest(func):
    if platform.system() == "Windows":
        func.__test__ = False
    return func


class LibcxxSettingTest(unittest.TestCase):

    def setUp(self):
        self.files = {"conanfile.py": file_content, "CMakeLists.txt": cmakelists}

    @nowintest
    def test_declared_stdlib_and_passed(self):
        client = TestClient()
        client.save(self.files)
        client.run("export lasote/testing")

        if platform.system() == "SunOS":
            client.run('install -s compiler=sun-cc -s compiler.libcxx=libCstd', ignore_error=False)
            client.run('build')
            self.assertIn("-library=Cstd", str(client.user_io.out))

            client.run('install -s compiler=sun-cc -s compiler.libcxx=libstdcxx', ignore_error=False)
            client.run('build')
            self.assertIn("-library=stdcxx4", str(client.user_io.out))

            client.run('install -s compiler=sun-cc -s compiler.libcxx=libstlport', ignore_error=False)
            client.run('build')
            self.assertIn("-library=stlport4", str(client.user_io.out))

        else:
            client.run('install -s compiler=clang -s compiler.version=3.3 -s compiler.libcxx=libstdc++ ', ignore_error=False)
            client.run('build')
            self.assertIn("-stdlib=libstdc++", str(client.user_io.out))
            self.assertIn("Found Define: _GLIBCXX_USE_CXX11_ABI=0", str(client.user_io.out))

            client.run('install -s compiler=clang -s compiler.version=3.3 -s compiler.libcxx=libstdc++11', ignore_error=False)
            client.run('build')
            self.assertIn("-stdlib=libstdc++", str(client.user_io.out))
            self.assertIn("Found Define: _GLIBCXX_USE_CXX11_ABI=1", str(client.user_io.out))

            client.run('install -s compiler=clang -s compiler.version=3.3 -s compiler.libcxx=libc++', ignore_error=False)
            client.run('build')
            self.assertIn("-stdlib=libc++", str(client.user_io.out))
            self.assertNotIn("Found Define: _GLIBCXX_USE_CXX11", str(client.user_io.out))

    def test_C_only(self):
        config = '''
    def config(self):
        del self.settings.compiler.libcxx # C package only
'''
        self.files["conanfile.py"] = self.files["conanfile.py"].replace('["cmake"]',
                                                                        '["cmake"]\n %s' % config)

        self.files["conanfile.py"] = self.files["conanfile.py"].replace("def build", "def nobuild")
        client = TestClient()
        client.save(self.files)
        client.run("export lasote/testing")
        client.run("install")
        # Also check that it not fails the config method with Visual Studio, because of the lack of libcxx
        client.run('install -s compiler="Visual Studio" -s compiler.version=12 -s compiler.runtime=MD', ignore_error=False)
        self.assertIn("Generated cmake created conanbuildinfo.cmake", str(client.user_io.out))

        conaninfo = load(os.path.join(client.current_folder, "conaninfo.txt"))
        self.assertNotIn("libcxx", conaninfo[:conaninfo.find("[full_settings]")])
        client.run('install test/1.9@lasote/testing -s compiler=gcc -s compiler.version=4.9 --build', ignore_error=False)

        # Now try to reuse the installed package defining libstc++11 for the new package
        newlib_content = '''
from conans import ConanFile, CMake

class ConanFileToolsTest(ConanFile):
    name = "test2"
    version = "1.9"
    settings = "os", "compiler", "arch", "build_type"
    url = "1"
    license = "2"
    export = ["CMakeLists.txt", "main.c"]
    generators = ["cmake"]
    requires = "test/1.9@lasote/testing"

    def build(self):
        pass
    '''
        new_client = TestClient(base_folder=client.base_folder)  # Share storage
        new_client.save({"conanfile.py": newlib_content, "CMakeLists.txt": cmakelists})
        new_client.run('install -s compiler=gcc -s compiler.libcxx=libstdc++11 -s compiler.version=4.9', ignore_error=False)
        # Package is found and everything is ok
        self.assertIn("Generated cmake created conanbuildinfo.cmake", str(new_client.user_io.out))

        # Try again without removing the setting, if we use libstdc++11, the C package won't be found
        self.files["conanfile.py"] = self.files["conanfile.py"].replace("def config", "def config222")
        client.save(self.files)
        client.run("export lasote/testing")
        client.run("install -s compiler=gcc -s compiler.libcxx=libstdc++ -s compiler.version=4.9")
        conaninfo = load(os.path.join(client.current_folder, "conaninfo.txt"))
        self.assertIn("libcxx", conaninfo[:conaninfo.find("[full_settings]")])
        client.run('install test/1.9@lasote/testing -s compiler=gcc --build -s compiler.libcxx=libstdc++ -s compiler.version=4.9', ignore_error=False)
        new_client.run('install -s compiler=gcc -s compiler.libcxx=libstdc++11 -s compiler.version=4.9', ignore_error=True)
        self.assertIn("Can't find a 'test/1.9@lasote/testing' package for the specified options and settings", str(new_client.user_io.out))
