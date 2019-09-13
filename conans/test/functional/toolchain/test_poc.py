# coding=utf-8

import platform
import textwrap
import unittest

from conans.client.toolchain.cmake import CMakeToolchain
from conans.test.utils.tools import TestClient


class ToolchainTestCase(unittest.TestCase):
    """
        We have a build_requires (wrapper over system CMake) that injects a variable
        using the CMake command line and another one using the environment. The project
        CMakeLists.txt should get both values
    """

    br = textwrap.dedent("""
        import os
        import stat
        from conans import ConanFile
        
        class Lib(ConanFile):
            name = "build_require"
            version = "version"
            
            def build(self):
                with open("cmake", "w") as f:
                    #f.write("#! /bin/sh\\n")
                    #f.write("{} $@ -DBR_WRAPPER:BOOL=True".format(cmake))

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
            options = {"toolchain": [True, False]}
            default_options = {"toolchain": True}
            exports = "*.cpp", "*.txt"
            
            build_requires = "build_require/version"
            
            def toolchain(self):
                tc = CMakeToolchain(self)
                tc.definitions["LIB_TOOLCHAIN"] = "LIB_TOOLCHAIN_VALUE"
                return tc
                
            def build(self):
                if self.options.toolchain:
                    self.run('cmake "%s" -DCMAKE_TOOLCHAIN_FILE=""" + CMakeToolchain.filename + """' % (self.source_folder))
                    self.run("cmake --build .")
                else:
                    cmake = CMake(self)
                    cmake.configure()
                    cmake.build()
    """)

    cmakelist = textwrap.dedent("""
        cmake_minimum_required(VERSION 2.8)
        project(App CXX)
    
        message("environment variable BUILD_REQUIRE=$ENV{BUILD_REQUIRE}")
        message("cmd argument BR_WRAPPER=${BR_WRAPPER}")
    
        add_executable(app src/app.cpp)
    """)

    app_cpp = textwrap.dedent("""
        #include <iostream>
        
        int main() {
            std::cout << "Hello Conan!" <<std::endl;
            return 0;
        }
    """)

    def setUp(self):
        self.t = TestClient(path_with_spaces=False)
        self.t.save({"conanfile.py": self.br})
        self.t.run("create .")

        self.t.save({"conanfile.py": self.conanfile,
                     "CMakeLists.txt": self.cmakelist,
                     "src/app.cpp": self.app_cpp}, clean_first=True)

    def _check_cmake_configure_output(self, output):
        # Same output for all the modes
        self.assertIn("-- Using Conan toolchain through {}.".format(CMakeToolchain.filename),
                      self.t.out)
        self.assertIn("environment variable BUILD_REQUIRE=build_require", self.t.out)
        self.assertIn("cmd argument BR_WRAPPER=True", self.t.out)

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

        self.t.run_command("./build/app")
        self.assertEqual("Hello Conan!", str(self.t.out).strip())

    def test_local_cmake(self):
        # The user will run this using their custom IDE, need to activate virtualenv
        def venv_comamnd(command):
            if platform.system() == "Windows":
                cmd_line = "activate.bat && {command} && deactivate.bat'"
            else:
                cmd_line = "bash -c 'source activate.sh && {command} && source deactivate.sh'"
            return cmd_line.format(command=command)

        with self.t.chdir("build"):
            self.t.run("install ..")

            # Configure (activate/deactivate venv)
            cmake_configure = venv_comamnd("cmake .. -DCMAKE_TOOLCHAIN_FILE={}".format(CMakeToolchain.filename))
            self.t.run_command(cmake_configure)
            self._check_cmake_configure_output(self.t.out)

            # Build
            self.t.run_command("cmake --build .")

        self.t.run_command("./build/app")
        self.assertEqual("Hello Conan!", str(self.t.out).strip())
