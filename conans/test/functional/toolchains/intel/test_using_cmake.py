import os
import platform

import pytest
import textwrap

from conan.tools.cmake import CMakeToolchain
from conan.tools.microsoft.visual import vcvars_command
from ._base import BaseIntelTestCase

from conans.test.assets.sources import gen_function_cpp


cmakelists_txt = textwrap.dedent("""
    cmake_minimum_required(VERSION 2.8.12)
    project(MyApp CXX)
    find_package(hello REQUIRED)
    set(CMAKE_VERBOSE_MAKEFILE ON)
    add_executable(${CMAKE_PROJECT_NAME} main.cpp)
    set_target_properties(${CMAKE_PROJECT_NAME} PROPERTIES DEBUG_POSTFIX "d")
    target_link_libraries(${CMAKE_PROJECT_NAME} PRIVATE hello::hello)

    install(TARGETS ${CMAKE_PROJECT_NAME}
        RUNTIME DESTINATION bin
        LIBRARY DESTINATION lib
        ARCHIVE DESTINATION lib
        PUBLIC_HEADER DESTINATION include
    )

""")

conanfile_py = textwrap.dedent("""
    from conans import ConanFile
    from conan.tools.cmake import CMake, CMakeToolchain

    class App(ConanFile):
        settings = 'os', 'arch', 'compiler', 'build_type'
        exports_sources = "CMakeLists.txt", "main.cpp"
        generators = "cmake_find_package_multi"
        requires = "hello/0.1"

        _cmake = None

        def _configure_cmake(self):
            if not self._cmake:
                self._cmake = CMake(self)
                self._cmake.configure()
            return self._cmake

        def generate(self):
            tc = CMakeToolchain(self)
            tc.generate()

        def build(self):
            cmake = self._configure_cmake()
            cmake.build()

        def package(self):
            cmake = self._configure_cmake()
            cmake.install()
    """)


@pytest.mark.tool_cmake
@pytest.mark.tool_icc
@pytest.mark.xfail(reason="Intel compiler not installed yet on CI")
@pytest.mark.skipif(platform.system() != "Windows", reason="Only for windows")
class CMakeIntelTestCase(BaseIntelTestCase):

    def test_use_cmake_toolchain(self):
        self.t.save({'profile': self.profile})
        self.t.run("new hello/0.1 -s")
        self.t.run("create . hello/0.1@ -pr:h=profile")

        app = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])

        # Prepare the actual consumer package
        self.t.save({"conanfile.py": conanfile_py,
                     "main.cpp": app,
                     "CMakeLists.txt": cmakelists_txt,
                     'profile': self.profile},
                    clean_first=True)

        # Build in the cache
        self.t.run("install . -pr:h=profile")
        self.assertIn("conanfile.py: Generator cmake_find_package_multi created helloTargets.cmake",
                      self.t.out)
        self.t.run("build .")
        self.assertIn("The CXX compiler identification is Intel 19.1", self.t.out)

        exe = os.path.join("Release", "MyApp.exe")
        self.t.run_command(exe)
        self.assertIn("main __INTEL_COMPILER1910", self.t.out)

        vcvars = vcvars_command(version="15", architecture="x64")
        dumpbind_cmd = '%s && dumpbin /dependents "%s"' % (vcvars, exe)
        self.t.run_command(dumpbind_cmd)
        self.assertIn("KERNEL32.dll", self.t.out)

        # Build locally
        os.unlink(os.path.join(self.t.current_folder, exe))

        self.t.run_command('cmake . -G "Visual Studio 15 2017" '
                           '-DCMAKE_TOOLCHAIN_FILE={}'.format(CMakeToolchain.filename))
        self.t.run_command('cmake --build . --config Release')

        self.t.run_command(exe)
        self.assertIn("main __INTEL_COMPILER1910", self.t.out)

        self.t.run_command(dumpbind_cmd)
        self.assertIn("KERNEL32.dll", self.t.out)
