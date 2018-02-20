import unittest
from conans.test.utils.tools import TestClient
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from nose.plugins.attrib import attr
from conans.util.files import load
from conans.model.ref import PackageReference
import os
from conans.paths import CONANFILE


@attr("slow")
class ConanTestTest(unittest.TestCase):

    def test_partial_reference(self):
        # Create two packages to test with the same test
        conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
'''
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("create . conan/stable")
        client.run("create . conan/testing")
        client.run("create . conan/foo")

        def test(conanfile_test, test_reference, path=None):
            path = path or "."
            client.save({os.path.join(path, CONANFILE): conanfile_test}, clean_first=True)
            client.run("test %s %s" % (path, test_reference))

        # Specify a valid name
        test('''
from conans import ConanFile

class HelloTestConan(ConanFile):
    requires = "Hello/0.1@conan/stable"
    def test(self):
        self.output.warn("Tested ok!")
''', "Hello/0.1@conan/stable")
        self.assertIn("Tested ok!", client.out)

        # Specify a complete reference but not matching with the requires, it's ok, the
        # require could be a tool or whatever
        test('''
from conans import ConanFile

class HelloTestConan(ConanFile):
    requires = "Hello/0.1@conan/stable"
    def test(self):
        self.output.warn("Tested ok!")
''', "Hello/0.1@conan/foo")
        self.assertIn("Tested ok!", client.out)

    def test_package_env_test(self):
        client = TestClient()
        conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    def package_info(self):
        self.env_info.PYTHONPATH.append("new/pythonpath/value")
        '''
        test_package = '''
import os
from conans import ConanFile

class HelloTestConan(ConanFile):
    requires = "Hello/0.1@lasote/testing"

    def build(self):
        assert("new/pythonpath/value" in os.environ["PYTHONPATH"])

    def test(self):
        assert("new/pythonpath/value" in os.environ["PYTHONPATH"])
'''

        client.save({"conanfile.py": conanfile, "test_package/conanfile.py": test_package})
        client.run("export . lasote/testing")
        client.run("test test_package Hello/0.1@lasote/testing --build missing")

    def fail_test_package_test(self):
        client = TestClient()
        conanfile = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    exports = "*"

    def package(self):
        self.copy("*")
"""
        test_conanfile = """
from conans import ConanFile, CMake
import os

class HelloReuseConan(ConanFile):
    requires = "Hello/0.1@lasote/stable"

    def test(self):
        pass
"""
        client.save({"conanfile.py": conanfile,
                     "FindXXX.cmake": "Hello FindCmake",
                     "test/conanfile.py": test_conanfile})
        client.run("create . lasote/stable")
        client.run("test test Hello/0.1@lasote/stable")
        ref = PackageReference.loads("Hello/0.1@lasote/stable:"
                                     "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertEqual("Hello FindCmake",
                         load(os.path.join(client.paths.package(ref), "FindXXX.cmake")))
        client.save({"FindXXX.cmake": "Bye FindCmake"})
        client.run("test test Hello/0.1@lasote/stable")  # Test do not rebuild the package
        self.assertEqual("Hello FindCmake",
                         load(os.path.join(client.paths.package(ref), "FindXXX.cmake")))
        client.run("create . lasote/stable")  # create rebuild the package
        self.assertEqual("Bye FindCmake",
                         load(os.path.join(client.paths.package(ref), "FindXXX.cmake")))

    def conan_test_test(self):

        # With classic requires
        conanfile = '''
from conans import ConanFile, CMake
import os

class HelloReuseConan(ConanFile):
    settings = "os", "compiler", "build_type", "arch"
    requires = "Hello0/0.1@lasote/stable"
    generators = "cmake"

    def build(self):
        cmake = CMake(self)
        self.run('cmake "%s" %s' % (self.source_folder, cmake.command_line))
        self.run("cmake --build . %s" % cmake.build_config)

    def test(self):
        # equal to ./bin/greet, but portable win: .\bin\greet
        self.run(os.sep.join([".","bin", "greet"]))
        '''
        self._test_with_conanfile(conanfile)

        # With requirements
        conanfile = '''
from conans import ConanFile, CMake
import os

class HelloReuseConan(ConanFile):
    settings = "os", "compiler", "build_type", "arch"
    generators = "cmake"

    def requirements(self):
        self.requires("Hello0/0.1@ lasote/stable")

    def build(self):
        cmake = CMake(self)
        self.run('cmake "%s" %s' % (self.source_folder, cmake.command_line))
        self.run("cmake --build . %s" % cmake.build_config)

    def test(self):
        # equal to ./bin/greet, but portable win: .\bin\greet
        self.run(os.sep.join([".","bin", "greet"]))
        '''
        self._test_with_conanfile(conanfile)

    def _test_with_conanfile(self, test_conanfile):
        client = TestClient()
        files = cpp_hello_conan_files("Hello0", "0.1")
        print_build = 'self.output.warn("BUILD_TYPE=>%s" % self.settings.build_type)'
        files[CONANFILE] = files[CONANFILE].replace("def build(self):",
                                                    'def build(self):\n        %s' % print_build)

        # Add build_type setting
        files[CONANFILE] = files[CONANFILE].replace(', "arch"',
                                                    ', "arch", "build_type"')

        cmakelist = """set(CMAKE_CXX_COMPILER_WORKS 1)
set(CMAKE_CXX_ABI_COMPILED 1)
project(MyHello CXX)
cmake_minimum_required(VERSION 2.8)

include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
conan_basic_setup()

ADD_EXECUTABLE(greet main.cpp)
TARGET_LINK_LIBRARIES(greet ${CONAN_LIBS})
"""
        files["test_package/CMakeLists.txt"] = cmakelist
        files["test_package/conanfile.py"] = test_conanfile
        files["test_package/main.cpp"] = files["main.cpp"]
        client.save(files)
        client.run("create . lasote/stable")
        client.run("test test_package Hello0/0.1@lasote/stable -s build_type=Release")

        self.assertNotIn("WARN: conanbuildinfo.txt file not found", client.user_io.out)
        self.assertNotIn("WARN: conanenv.txt file not found", client.user_io.out)
        self.assertIn('Hello Hello0', client.user_io.out)
        client.run("test test_package Hello0/0.1@lasote/stable -s Hello0:build_type=Debug "
                   "-o Hello0:language=1 --build missing")
        self.assertIn('Hola Hello0', client.user_io.out)
        self.assertIn('BUILD_TYPE=>Debug', client.user_io.out)
