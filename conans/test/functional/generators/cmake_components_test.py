import textwrap
import unittest

from nose.plugins.attrib import attr

from conans.test.utils.tools import TestClient


@attr('slow')
class CMakeGeneratorsWithComponentsTest(unittest.TestCase):

    def _test(self, conanfile_greetings=None, cmakelists_greetings=None, conanfile_world=None,
              cmakelists_world=None, test_package_cmakelists=None):
        client = TestClient()
        _conanfile_greetings = textwrap.dedent("""
            from conans import ConanFile, CMake

            class GreetingsConan(ConanFile):
                name = "greetings"
                version = "0.0.1"
                settings = "os", "compiler", "build_type", "arch"
                generators = "cmake"
                exports_sources = "src/*"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure(source_folder="src")
                    cmake.build()

                def package(self):
                    self.copy("*.h", dst="include", src="src")
                    self.copy("*.lib", dst="lib", keep_path=False)
                    self.copy("*.dll", dst="bin", keep_path=False)
                    self.copy("*.dylib*", dst="lib", keep_path=False)
                    self.copy("*.so", dst="lib", keep_path=False)
                    self.copy("*.a", dst="lib", keep_path=False)

                def package_info(self):
                    self.cpp_info.components["hello"].libs = ["hello"]
                    self.cpp_info.components["bye"].libs = ["bye"]
            """)
        hello_h = textwrap.dedent("""
            #pragma once

            void hello(std::string noun);
            """)
        hello_cpp = textwrap.dedent("""
            #include <iostream>
            #include "hello.h"

            void hello(std::string noun) {
                std::cout << "Hello " << noun << "!" << std::endl;
            }
            """)
        bye_h = textwrap.dedent("""
            #pragma once

            void bye(std::string noun);
            """)
        bye_cpp = textwrap.dedent("""
            #include <iostream>
            #include "bye.h"

            void bye(std::string noun) {
                std::cout << "Bye " << noun << "!" << std::endl;
            }
            """)
        _cmakelists_greetings = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.0)
            project(greetings CXX)

            include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
            conan_basic_setup()

            add_library(hello hello.cpp)
            add_library(bye bye.cpp)
            """)
        client.save({"conanfile.py": conanfile_greetings or _conanfile_greetings,
                     "src/CMakeLists.txt": cmakelists_greetings or _cmakelists_greetings,
                     "src/hello.h": hello_h,
                     "src/hello.cpp": hello_cpp,
                     "src/bye.h": bye_h,
                     "src/bye.cpp": bye_cpp})
        client.run("create .")

        _conanfile_world = textwrap.dedent("""
            from conans import ConanFile, CMake

            class WorldConan(ConanFile):
                name = "world"
                version = "0.0.1"
                settings = "os", "compiler", "build_type", "arch"
                generators = "cmake_find_package"
                exports_sources = "src/*"
                requires = "greetings/0.0.1"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure(source_folder="src")
                    cmake.build()

                def package(self):
                    self.copy("*.h", dst="include", src="src")
                    self.copy("*.lib", dst="lib", keep_path=False)
                    self.copy("*.dll", dst="bin", keep_path=False)
                    self.copy("*.dylib*", dst="lib", keep_path=False)
                    self.copy("*.so", dst="lib", keep_path=False)
                    self.copy("*.a", dst="lib", keep_path=False)

                def package_info(self):
                    self.cpp_info.components["helloworld"].requires = ["greetings::greetings"]
                    self.cpp_info.components["helloworld"].libs = ["helloworld"]
                    self.cpp_info.components["worldall"].requires = ["greetings::greetings", "helloworld"]
                    self.cpp_info.components["worldall"].libs = ["worldall"]
        """)
        helloworld_h = textwrap.dedent("""
            #pragma once

            void helloWorld();
            """)
        helloworld_cpp = textwrap.dedent("""
            #include <iostream>
            #include "hello.h"
            #include "helloworld.h"

            void helloWorld() {
                hello("World");
            }
            """)
        worldall_h = textwrap.dedent("""
            #pragma once

            void worldAll();
            """)
        worldall_cpp = textwrap.dedent("""
            #include <iostream>
            #include "bye.h"
            #include "helloworld.h"
            #include "worldall.h"

            void worldAll() {
                helloWorld();
                bye("World");
            }
            """)
        _cmakelists_world = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.0)
            project(world CXX)

            find_package(greetings COMPONENTS hello)

            add_library(helloworld helloworld.cpp)
            target_link_libraries(helloworld greetings::greetings)

            find_package(greetings COMPONENTS bye)

            add_library(worldall worldall.cpp)
            target_link_libraries(worldall helloworld greetings::greetings)
        """)
        test_package_conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile, CMake

            class WorldTestConan(ConanFile):
                settings = "os", "compiler", "build_type", "arch"
                generators = "cmake_find_package"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                    cmake.build()

                def test(self):
                    os.chdir("bin")
                    self.run(".%sexample" % os.sep)
                    # self.run(".%sexample2" % os.sep)
        """)
        test_package_example_cpp = textwrap.dedent("""
            #include <iostream>
            #include "worldall.h"

            int main() {
                worldAll();
            }
            """)
        _test_package_cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.0)
            project(PackageTest CXX)

            set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/bin)
            set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_RELEASE ${CMAKE_RUNTIME_OUTPUT_DIRECTORY})
            set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_RELWITHDEBINFO ${CMAKE_RUNTIME_OUTPUT_DIRECTORY})
            set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_MINSIZEREL ${CMAKE_RUNTIME_OUTPUT_DIRECTORY})
            set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_DEBUG ${CMAKE_RUNTIME_OUTPUT_DIRECTORY})

            find_package(world)
            
            get_target_property(tmp world::worldall INTERFACE_LINK_LIBRARIES)
            message("world::worldall target libs: ${tmp}")

            add_executable(example example.cpp)
            target_link_libraries(example world::worldall)

            # add_executable(example2 example.cpp)
            # target_link_libraries(example2 world::world)
            """)
        client.save({"conanfile.py": conanfile_world or _conanfile_world,
                     "src/CMakeLists.txt": cmakelists_world or _cmakelists_world,
                     "src/helloworld.h": helloworld_h,
                     "src/helloworld.cpp": helloworld_cpp,
                     "src/worldall.h": worldall_h,
                     "src/worldall.cpp": worldall_cpp,
                     "test_package/conanfile.py": test_package_conanfile,
                     "test_package/CMakeLists.txt": test_package_cmakelists or _test_package_cmakelists,
                     "test_package/example.cpp": test_package_example_cpp})
        client.run("create .")
        print(client.out)
        return client.out

    def basic_test(self):
        client = TestClient()
        conanfile_greetings = textwrap.dedent("""
                    from conans import ConanFile, CMake

                    class GreetingsConan(ConanFile):
                        name = "greetings"
                        version = "0.0.1"
                        settings = "os", "compiler", "build_type", "arch"
                        generators = "cmake"
                        exports_sources = "src/*"

                        def build(self):
                            cmake = CMake(self)
                            cmake.configure(source_folder="src")
                            cmake.build()

                        def package(self):
                            self.copy("*.h", dst="include", src="src")
                            self.copy("*.lib", dst="lib", keep_path=False)
                            self.copy("*.dll", dst="bin", keep_path=False)
                            self.copy("*.dylib*", dst="lib", keep_path=False)
                            self.copy("*.so", dst="lib", keep_path=False)
                            self.copy("*.a", dst="lib", keep_path=False)

                        def package_info(self):
                            self.cpp_info.components["hello"].libs = ["hello"]
                            self.cpp_info.components["bye"].libs = ["bye"]
                    """)
        hello_h = textwrap.dedent("""
                    #pragma once

                    void hello(std::string noun);
                    """)
        hello_cpp = textwrap.dedent("""
                    #include <iostream>
                    #include "hello.h"

                    void hello(std::string noun) {
                        std::cout << "Hello " << noun << "!" << std::endl;
                    }
                    """)
        bye_h = textwrap.dedent("""
                    #pragma once

                    void bye(std::string noun);
                    """)
        bye_cpp = textwrap.dedent("""
                    #include <iostream>
                    #include "bye.h"

                    void bye(std::string noun) {
                        std::cout << "Bye " << noun << "!" << std::endl;
                    }
                    """)
        cmakelists_greetings = textwrap.dedent("""
                    cmake_minimum_required(VERSION 3.0)
                    project(greetings CXX)

                    include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
                    conan_basic_setup()

                    add_library(hello hello.cpp)
                    add_library(bye bye.cpp)
                    """)
        test_package_greetings_conanfile = textwrap.dedent("""
                    import os
                    from conans import ConanFile, CMake

                    class GreetingsTestConan(ConanFile):
                        settings = "os", "compiler", "build_type", "arch"
                        generators = "cmake_find_package"

                        def build(self):
                            cmake = CMake(self)
                            cmake.configure()
                            cmake.build()

                        def test(self):
                            os.chdir("bin")
                            self.run(".%sexample" % os.sep)
                    """)
        test_package_greetings_cpp = textwrap.dedent("""
                    #include <iostream>
                    #include "hello.h"
                    #include "bye.h"

                    int main() {
                        hello("Moon");
                        bye("Moon");
                    }
                    """)
        test_package_greetings_cmakelists = textwrap.dedent("""
                    cmake_minimum_required(VERSION 3.0)
                    project(PackageTest CXX)

                    set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/bin)
                    set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_RELEASE ${CMAKE_RUNTIME_OUTPUT_DIRECTORY})
                    set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_RELWITHDEBINFO ${CMAKE_RUNTIME_OUTPUT_DIRECTORY})
                    set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_MINSIZEREL ${CMAKE_RUNTIME_OUTPUT_DIRECTORY})
                    set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_DEBUG ${CMAKE_RUNTIME_OUTPUT_DIRECTORY})

                    find_package(greetings)

                    get_target_property(tmp greetings::greetings INTERFACE_LINK_LIBRARIES)
                    message("greetings::greetings target libs: ${tmp}")
                    get_target_property(tmp greetings::hello INTERFACE_LINK_LIBRARIES)
                    message("greetings::Hello target libs: ${tmp}")
                    get_target_property(tmp greetings::bye INTERFACE_LINK_LIBRARIES)
                    message("greetings::bye target libs: ${tmp}")
                    get_target_property(tmp bye IMPORTED_LOCATION)
                    message("bye imported location: ${tmp}")

                    add_executable(example example.cpp)
                    target_link_libraries(example greetings::greetings)
                    """)
        client.save({"conanfile.py": conanfile_greetings,
                     "src/CMakeLists.txt": cmakelists_greetings,
                     "src/hello.h": hello_h,
                     "src/hello.cpp": hello_cpp,
                     "src/bye.h": bye_h,
                     "src/bye.cpp": bye_cpp,
                     "test_package/conanfile.py": test_package_greetings_conanfile,
                     "test_package/example.cpp": test_package_greetings_cpp,
                     "test_package/CMakeLists.txt": test_package_greetings_cmakelists})
        client.run("create .")

    def component_depends_on_full_package_test(self):
        out = self._test()
        self.assertIn("Hello World!", out)
        self.assertIn("Bye World!", out)

    def find_package_general_test(self):
        conanfile_greetings = textwrap.dedent("""
            from conans import ConanFile, CMake

            class GreetingsConan(ConanFile):
                name = "greetings"
                version = "0.0.1"
                settings = "os", "compiler", "build_type", "arch"
                generators = "cmake"
                exports_sources = "src/*"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure(source_folder="src")
                    cmake.build()

                def package(self):
                    self.copy("*.h", dst="include", src="src")
                    self.copy("*.lib", dst="lib", keep_path=False)
                    self.copy("*.dll", dst="bin", keep_path=False)
                    self.copy("*.dylib*", dst="lib", keep_path=False)
                    self.copy("*.so", dst="lib", keep_path=False)
                    self.copy("*.a", dst="lib", keep_path=False)

                def package_info(self):
                    self.cpp_info.names["cmake_find_package"] = "Greetings"
                    self.cpp_info.components["hello"].names["cmake_find_package"] = "Hello"
                    self.cpp_info.components["hello"].libs = ["hello"]
                    self.cpp_info.components["bye"].names["cmake_find_package"] = "Bye"
                    self.cpp_info.components["bye"].libs = ["bye"]
        """)

        conanfile_world = textwrap.dedent("""
            from conans import ConanFile, CMake

            class WorldConan(ConanFile):
                name = "world"
                version = "0.0.1"
                settings = "os", "compiler", "build_type", "arch"
                generators = "cmake_find_package"
                exports_sources = "src/*"
                requires = "greetings/0.0.1"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure(source_folder="src")
                    cmake.build()

                def package(self):
                    self.copy("*.h", dst="include", src="src")
                    self.copy("*.lib", dst="lib", keep_path=False)
                    self.copy("*.dll", dst="bin", keep_path=False)
                    self.copy("*.dylib*", dst="lib", keep_path=False)
                    self.copy("*.so", dst="lib", keep_path=False)
                    self.copy("*.a", dst="lib", keep_path=False)

                def package_info(self):
                    self.cpp_info.names["cmake_find_package"] = "World"
                    self.cpp_info.components["helloworld"].names["cmake_find_package"] = "Helloworld"
                    self.cpp_info.components["helloworld"].requires = ["greetings::hello"]
                    self.cpp_info.components["helloworld"].libs = ["Helloworld"]
                    self.cpp_info.components["worldall"].names["cmake_find_package"] = "Worldall"
                    self.cpp_info.components["worldall"].requires = ["greetings::bye", "helloworld"]
                    self.cpp_info.components["worldall"].libs = ["Worldall"]
        """)
        cmakelists_world = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.0)
            project(world CXX)

            find_package(Greetings)

            add_library(Helloworld helloworld.cpp)
            target_link_libraries(Helloworld Greetings::Hello)

            add_library(Worldall worldall.cpp)
            target_link_libraries(Worldall Helloworld Greetings::Bye)
        """)
        test_package_cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.0)
            project(PackageTest CXX)

            set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/bin)
            set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_RELEASE ${CMAKE_RUNTIME_OUTPUT_DIRECTORY})
            set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_RELWITHDEBINFO ${CMAKE_RUNTIME_OUTPUT_DIRECTORY})
            set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_MINSIZEREL ${CMAKE_RUNTIME_OUTPUT_DIRECTORY})
            set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_DEBUG ${CMAKE_RUNTIME_OUTPUT_DIRECTORY})

            find_package(World)

            get_target_property(tmp World::Worldall INTERFACE_LINK_LIBRARIES)
            message("World::Worldall target libs: ${tmp}")
            get_target_property(tmp World::Helloworld INTERFACE_LINK_LIBRARIES)
            message("World::Helloworld target libs: ${tmp}")
            get_target_property(tmp Greetings::Bye INTERFACE_LINK_LIBRARIES)
            message("Greetings::Bye target libs: ${tmp}")
            get_target_property(tmp Greetings::Hello INTERFACE_LINK_LIBRARIES)
            message("Greetings::Hello target libs: ${tmp}")

            add_executable(example example.cpp)
            target_link_libraries(example World::Worldall)

            # add_executable(example2 example.cpp)
            # target_link_libraries(example2 World::World)
            """)
        out = self._test(conanfile_greetings=conanfile_greetings,
                         conanfile_world=conanfile_world, cmakelists_world=cmakelists_world,
                         test_package_cmakelists=test_package_cmakelists)
        self.assertIn("Hello World!", out)
        self.assertIn("Bye World!", out)

    def find_package_components_test(self):
        conanfile2 = textwrap.dedent("""
            from conans import ConanFile, CMake

            class WorldConan(ConanFile):
                name = "world"
                version = "0.0.1"
                settings = "os", "compiler", "build_type", "arch"
                generators = "cmake_find_package"
                exports_sources = "src/*"
                requires = "greetings/0.0.1"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure(source_folder="src")
                    cmake.build()

                def package(self):
                    self.copy("*.h", dst="include", src="src")
                    self.copy("*.lib", dst="lib", keep_path=False)
                    self.copy("*.dll", dst="bin", keep_path=False)
                    self.copy("*.dylib*", dst="lib", keep_path=False)
                    self.copy("*.so", dst="lib", keep_path=False)
                    self.copy("*.a", dst="lib", keep_path=False)

                def package_info(self):
                    self.cpp_info.components["helloworld"].requires = ["greetings::hello"]
                    self.cpp_info.components["helloworld"].libs = ["helloworld"]
                    self.cpp_info.components["worldall"].requires = ["greetings::bye", "helloworld"]
                    self.cpp_info.components["worldall"].libs = ["worldall"]
        """)
        cmakelists2 = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.0)
            project(world CXX)

            find_package(greetings COMPONENTS hello)

            add_library(helloworld helloworld.cpp)
            target_link_libraries(helloworld greetings::hello)

            find_package(greetings COMPONENTS bye)

            add_library(worldall worldall.cpp)
            target_link_libraries(worldall helloworld greetings::bye)
        """)
        out = self._test(conanfile_world=conanfile2, cmakelists_world=cmakelists2)
        self.assertIn("Hello World!", out)
        self.assertIn("Bye World!", out)

    def recipe_with_components_requiring_recipe_without_components_test(self):
        conanfile1 = textwrap.dedent("""
            from conans import ConanFile, CMake

            class GreetingsConan(ConanFile):
                name = "greetings"
                version = "0.0.1"
                settings = "os", "compiler", "build_type", "arch"
                generators = "cmake"
                exports_sources = "src/*"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure(source_folder="src")
                    cmake.build()

                def package(self):
                    self.copy("*.h", dst="include", src="src")
                    self.copy("*.lib", dst="lib", keep_path=False)
                    self.copy("*.dll", dst="bin", keep_path=False)
                    self.copy("*.dylib*", dst="lib", keep_path=False)
                    self.copy("*.so", dst="lib", keep_path=False)
                    self.copy("*.a", dst="lib", keep_path=False)

                def package_info(self):
                    self.cpp_info.libs = ["hello", "bye"]
        """)
        out = self._test(conanfile_greetings=conanfile1)
        self.assertIn("Hello World!", out)
        self.assertIn("Bye World!", out)

    def component_not_found_test(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile, CMake

            class GreetingsConan(ConanFile):
                name = "greetings"
                version = "0.0.1"
                settings = "os", "compiler", "build_type", "arch"

                def package_info(self):
                    self.cpp_info.components["hello"].libs = ["hello"]
        """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create conanfile.py")

        conanfile = textwrap.dedent("""
            from conans import ConanFile, CMake

            class WorldConan(ConanFile):
                name = "world"
                version = "0.0.1"
                settings = "os", "compiler", "build_type", "arch"
                requires = "greetings/0.0.1"

                def package_info(self):
                    self.cpp_info.components["helloworld"].requires = ["greetings::non-existent"]
                    self.cpp_info.components["helloworld"].libs = ["helloworld"]
        """)
        client.save({"conanfile.py": conanfile})
        client.run("create conanfile.py")
        client.run("install world/0.0.1@ -g cmake_find_package", assert_error=True)
        self.assertIn("ERROR: Component 'greetings::non-existent' not found in 'greetings' "
                      "package requirement", client.out)
