# coding=utf-8

import os
import platform
import textwrap
import unittest

from nose.plugins.attrib import attr

from conans.client.toolchain.cmake import CMakeToolchain
from conans.test.utils.tools import TestClient


@attr("toolchain")
@unittest.skip("Not working on environment yet")
class ToolchainTestCase(unittest.TestCase):
    """
        We have a build_requires (wrapper over system CMake) that injects a variable
        using the CMake command line and another one using the environment. The project
        CMakeLists.txt should get both values
    """

    cmake_conanfile = textwrap.dedent("""
        import os
        import stat
        from conans import ConanFile
        
        class CMakeBuilRequire(ConanFile):
            name = "build_require"
            version = "version"
            
            def build(self):
                with open("cmake", "w") as f:
                    f.write("#! /bin/sh - \\n")
                    f.write("while test $# -gt 0\\n")
                    f.write("do\\n")
                    f.write("    case \\"$1\\" in\\n")
                    f.write("        --build) /usr/local/bin/cmake $@\\n")
                    f.write("            ;;\\n")
                    f.write("        *) /usr/local/bin/cmake $@ -DBR_WRAPPER:BOOL=True\\n")
                    f.write("            ;;\\n")
                    f.write("    esac\\n")
                    f.write("    shift\\n")
                    f.write("done\\n")
                    f.write("exit 0\\n")
                    
                os.chmod("cmake", 0o555)
                    
            def package(self):
                self.copy("cmake", dst="bin")
            
            def package_info(self):
                self.env_info.PATH.append(os.path.join(self.package_folder, "bin"))
                self.env_info.BUILD_REQUIRE = "build_require"
    """)

    conanfile = textwrap.dedent("""
        from conans import ConanFile, CMake, CMakeToolchain
        
        class App(ConanFile):
            name = "app"
            version = "version"
            settings = "os", "arch", "compiler", "build_type"
            default_options = {"requirement:shared": True}
            exports = "*.cpp", "*.txt"
            generators = "cmake_find_package"
            
            build_requires = "build_require/version"
            requires = "requirement/version"
            
            def toolchain(self):
                tc = CMakeToolchain(self)
                tc.definitions["LIB_TOOLCHAIN"] = "LIB_TOOLCHAIN_VALUE"
                return tc
                
            def build(self):
                # A build helper could be easily added to replace this
                self.run('cmake "%s" -DCMAKE_TOOLCHAIN_FILE=""" + CMakeToolchain.filename + """' % (self.source_folder))
                self.run("cmake --build .")
    """)

    cmakelist = textwrap.dedent("""
        message("**************** CMAKELISTS *************")
        message("CMAKE_GENERATOR: ${CMAKE_GENERATOR}")
        cmake_minimum_required(VERSION 2.8)
        message("**************** CMAKELISTS::project *************")
        message("CMAKE_GENERATOR: ${CMAKE_GENERATOR}")
        project(App CXX)
        
        message("**************** CMAKELISTS:: *************")
        message("CMAKE_GENERATOR: ${CMAKE_GENERATOR}")
        message("environment variable BUILD_REQUIRE=$ENV{BUILD_REQUIRE}")
        message("cmd argument BR_WRAPPER=${BR_WRAPPER}")
        message("environment variable TOOLCHAIN_ENV=$ENV{TOOLCHAIN_ENV}")
        message("variable TOOLCHAIN_VAR=${TOOLCHAIN_VAR}")
    
        find_package(requirement REQUIRED)
    
        add_executable(app src/app.cpp)
        target_link_libraries(app requirement::requirement)
    """)

    app_cpp = textwrap.dedent("""
        #include <iostream>
        #include "hello.h"
        
        int main() {
            hello();
            return 0;
        }
    """)

    def setUp(self):
        self.t = TestClient(path_with_spaces=False)
        # Create the CMake build requires
        self.t.save({"conanfile.py": self.cmake_conanfile})
        self.t.run("create .")

        # Create the 'Requirement' require
        self.t.run("new requirement/version -s")
        self.t.run("create . requirement/version@ -o shared=True")

        # Prepare the actual consumer package
        self.t.save({"conanfile.py": self.conanfile,
                     "CMakeLists.txt": self.cmakelist,
                     "src/app.cpp": self.app_cpp}, clean_first=True)

    def _check_cmake_configure_output(self, output):
        # Same output for all the modes
        self.assertIn("Using Conan toolchain through {}.".format(CMakeToolchain.filename),
                      self.t.out)
        self.assertIn("environment variable BUILD_REQUIRE=build_require", self.t.out)
        self.assertIn("cmd argument BR_WRAPPER=True", self.t.out)
        self.assertIn("environment variable TOOLCHAIN_ENV=toolchain_environment", self.t.out)
        self.assertIn("variable TOOLCHAIN_VAR=toolchain_variable", self.t.out)

    def test_cache_create(self):
        self.t.run("create .")
        self._check_cmake_configure_output(self.t.out)

    def test_cache_install(self):
        self.t.run("export .")
        self.t.run("install app/version@ --build app")
        self._check_cmake_configure_output(self.t.out)

    def test_local_conan(self):
        # Conan local workflow
        with self.t.chdir("build"):
            self.t.run("install ..")
            self.t.run("build ..")
            self._check_cmake_configure_output(self.t.out)

        run_app = venv_comamnd("./build/app", scripts_folder="build")
        self.t.run_command(run_app)
        self.assertEqual("Hello World Release!", str(self.t.out).strip())

    def test_local_cmake(self):
        with self.t.chdir("build"):
            self.t.run("install ..")

            # Configure (activate/deactivate venv)
            cmake_configure = venv_comamnd("cmake .. -DCMAKE_TOOLCHAIN_FILE={}".format(CMakeToolchain.filename))
            self.t.run_command(cmake_configure)
            self._check_cmake_configure_output(self.t.out)

            # Build
            self.t.run_command("cmake --build .")  # This doesn't need to run inside the venv

        run_app = venv_comamnd("./build/app", scripts_folder="build")
        self.t.run_command(run_app)
        self.assertEqual("Hello World Release!", str(self.t.out).strip())


def venv_comamnd(command, scripts_folder="."):
    # Helper function to activate/deactivate the virtualenv
    activate = os.path.join(scripts_folder, "activate")
    deactivate = os.path.join(scripts_folder, "deactivate")

    if platform.system() == "Windows":
        cmd_line = "{}.bat && {{command}} && {}.bat'".format(activate, deactivate)
    else:
        cmd_line = "bash -c 'source {}.sh && {{command}} && source {}.sh'".format(activate, deactivate)
    return cmd_line.format(command=command)
