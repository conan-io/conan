import textwrap
import unittest

from nose.plugins.attrib import attr

from conans.model.ref import ConanFileReference
from conans.test.utils.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


@attr('slow')
class CMakeGeneratorsWithComponentsTest(unittest.TestCase):

    @staticmethod
    def _create_greetings(client, custom_names=False, components=True, test=False):
        hello_h = textwrap.dedent("""
            #pragma once
            void hello(std::string noun);
            """)

        hello_cpp = textwrap.dedent("""
            #include <iostream>
            #include <string>

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
            #include <string>

            #include "bye.h"

            void bye(std::string noun) {
                std::cout << "Bye " << noun << "!" << std::endl;
            }
            """)

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
                    self.copy("*.a", dst="lib", keep_path=False)

                def package_info(self):
                %s
            """)
        if components:
            info = textwrap.dedent("""
                        self.cpp_info.components["hello"].libs = ["hello"]
                        self.cpp_info.components["bye"].libs = ["bye"]
                        """)
            if custom_names:
                info += textwrap.dedent("""
                        self.cpp_info.names["cmake_find_package"] = "Greetings"
                        self.cpp_info.components["hello"].names["cmake_find_package"] = "Hello"
                        self.cpp_info.components["bye"].names["cmake_find_package"] = "Bye"
                        """)
        else:
            info = textwrap.dedent("""
                        self.cpp_info.libs = ["hello", "bye"]
                        """)
        wrapper = textwrap.TextWrapper(width=81, initial_indent="   ", subsequent_indent="        ")
        conanfile_greetings = conanfile_greetings % wrapper.fill(info)

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
                generators = "cmake", "cmake_find_package"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                    cmake.build()

                def test(self):
                    os.chdir("bin")
                    self.run(".%sexample" % os.sep)
            """)
        test_package_greetings_cpp = textwrap.dedent("""
            #include <string>

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

            include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
            conan_basic_setup()

            find_package(greetings)

            add_executable(example example.cpp)
            target_link_libraries(example greetings::greetings)
            """)
        client.save({"conanfile.py": conanfile_greetings,
                     "src/CMakeLists.txt": cmakelists_greetings,
                     "src/hello.h": hello_h,
                     "src/hello.cpp": hello_cpp,
                     "src/bye.h": bye_h,
                     "src/bye.cpp": bye_cpp})
        if test:
            client.save({"test_package/conanfile.py": test_package_greetings_conanfile,
                         "test_package/example.cpp": test_package_greetings_cpp,
                         "test_package/CMakeLists.txt": test_package_greetings_cmakelists})
        client.run("create .")

    @staticmethod
    def _create_world(client, conanfile=None, cmakelists=None, test_cmakelists=None):
        _conanfile_world = textwrap.dedent("""
            from conans import ConanFile, CMake

            class WorldConan(ConanFile):
                name = "world"
                version = "0.0.1"
                settings = "os", "compiler", "build_type", "arch"
                generators = "cmake_find_package", "cmake"
                exports_sources = "src/*"
                requires = "greetings/0.0.1"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure(source_folder="src")
                    cmake.build()

                def package(self):
                    self.copy("*.h", dst="include", src="src")
                    self.copy("*.lib", dst="lib", keep_path=False)
                    self.copy("*.a", dst="lib", keep_path=False)

                def package_info(self):
                    self.cpp_info.components["helloworld"].requires = ["greetings::hello"]
                    self.cpp_info.components["helloworld"].libs = ["helloworld"]
                    self.cpp_info.components["worldall"].requires = ["helloworld",
                                                                     "greetings::greetings"]
                    self.cpp_info.components["worldall"].libs = ["worldall"]
            """)
        helloworld_h = textwrap.dedent("""
            #pragma once

            void helloWorld();
            """)
        helloworld_cpp = textwrap.dedent("""
            #include <string>
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
            #include <string>
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

            include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
            conan_basic_setup()

            find_package(greetings COMPONENTS hello)

            add_library(helloworld helloworld.cpp)
            target_link_libraries(helloworld greetings::hello)

            find_package(greetings COMPONENTS bye)

            add_library(worldall worldall.cpp)
            target_link_libraries(worldall helloworld greetings::greetings)
            """)
        test_conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile, CMake

            class WorldTestConan(ConanFile):
                settings = "os", "compiler", "build_type", "arch"
                generators = "cmake", "cmake_find_package"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                    cmake.build()

                def test(self):
                    os.chdir("bin")
                    self.run(".%sexample" % os.sep)
                    self.run(".%sexample2" % os.sep)
            """)
        test_example_cpp = textwrap.dedent("""
            #include "worldall.h"

            int main() {
                worldAll();
            }
            """)
        _test_cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.0)
            project(PackageTest CXX)

            include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
            conan_basic_setup()

            find_package(world)

            add_executable(example example.cpp)
            target_link_libraries(example world::worldall)

            add_executable(example2 example.cpp)
            target_link_libraries(example2 world::world)
            """)
        client.save({"conanfile.py": conanfile or _conanfile_world,
                     "src/CMakeLists.txt": cmakelists or _cmakelists_world,
                     "src/helloworld.h": helloworld_h,
                     "src/helloworld.cpp": helloworld_cpp,
                     "src/worldall.h": worldall_h,
                     "src/worldall.cpp": worldall_cpp,
                     "test_package/conanfile.py": test_conanfile,
                     "test_package/CMakeLists.txt": test_cmakelists or _test_cmakelists,
                     "test_package/example.cpp": test_example_cpp})
        client.run("create .")

    def basic_test(self):
        client = TestClient()
        self._create_greetings(client, test=True)
        self.assertIn("Hello Moon!", client.out)
        self.assertIn("Bye Moon!", client.out)
        self._create_world(client)
        self.assertIn("Hello World!", client.out)
        self.assertIn("Bye World!", client.out)

    def find_package_general_test(self):
        client = TestClient()
        self._create_greetings(client, custom_names=True)

        conanfile = textwrap.dedent("""
            from conans import ConanFile, CMake

            class WorldConan(ConanFile):
                name = "world"
                version = "0.0.1"
                settings = "os", "compiler", "build_type", "arch"
                generators = "cmake", "cmake_find_package"
                exports_sources = "src/*"
                requires = "greetings/0.0.1"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure(source_folder="src")
                    cmake.build()

                def package(self):
                    self.copy("*.h", dst="include", src="src")
                    self.copy("*.lib", dst="lib", keep_path=False)
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
        cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.0)
            project(world CXX)

            include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
            conan_basic_setup()

            find_package(Greetings)

            add_library(Helloworld helloworld.cpp)
            target_link_libraries(Helloworld Greetings::Hello)

            add_library(Worldall worldall.cpp)
            target_link_libraries(Worldall Helloworld Greetings::Bye)
        """)
        test_cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.0)
            project(PackageTest CXX)

            include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
            conan_basic_setup()

            find_package(World)

            add_executable(example example.cpp)
            target_link_libraries(example World::Worldall)

            add_executable(example2 example.cpp)
            target_link_libraries(example2 World::World)
            """)
        self._create_world(client, conanfile=conanfile, cmakelists=cmakelists,
                           test_cmakelists=test_cmakelists)
        self.assertIn("Hello World!", client.out)
        self.assertIn("Bye World!", client.out)

    def find_package_components_test(self):
        client = TestClient()
        self._create_greetings(client)
        conanfile2 = textwrap.dedent("""
            from conans import ConanFile, CMake

            class WorldConan(ConanFile):
                name = "world"
                version = "0.0.1"
                settings = "os", "compiler", "build_type", "arch"
                generators = "cmake", "cmake_find_package"
                exports_sources = "src/*"
                requires = "greetings/0.0.1"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure(source_folder="src")
                    cmake.build()

                def package(self):
                    self.copy("*.h", dst="include", src="src")
                    self.copy("*.lib", dst="lib", keep_path=False)
                    self.copy("*.a", dst="lib", keep_path=False)

                def package_info(self):
                    self.cpp_info.components["helloworld"].requires = ["greetings::hello"]
                    self.cpp_info.components["helloworld"].libs = ["helloworld"]
                    self.cpp_info.components["worldall"].requires = ["helloworld", "greetings::bye"]
                    self.cpp_info.components["worldall"].libs = ["worldall"]
        """)
        cmakelists2 = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.0)
            project(world CXX)

            include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
            conan_basic_setup()

            find_package(greetings COMPONENTS hello)

            add_library(helloworld helloworld.cpp)
            target_link_libraries(helloworld greetings::hello)

            find_package(greetings COMPONENTS bye)

            add_library(worldall worldall.cpp)
            target_link_libraries(worldall helloworld greetings::bye)
        """)
        self._create_world(client, conanfile=conanfile2, cmakelists=cmakelists2)
        self.assertIn("Hello World!", client.out)
        self.assertIn("Bye World!", client.out)

    def recipe_with_components_requiring_recipe_without_components_test(self):
        client = TestClient()
        self._create_greetings(client, components=False)

        conanfile = textwrap.dedent("""
            from conans import ConanFile, CMake

            class WorldConan(ConanFile):
                name = "world"
                version = "0.0.1"
                settings = "os", "compiler", "build_type", "arch"
                generators = "cmake_find_package", "cmake"
                exports_sources = "src/*"
                requires = "greetings/0.0.1"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure(source_folder="src")
                    cmake.build()

                def package(self):
                    self.copy("*.h", dst="include", src="src")
                    self.copy("*.lib", dst="lib", keep_path=False)
                    self.copy("*.a", dst="lib", keep_path=False)

                def package_info(self):
                    self.cpp_info.components["helloworld"].requires = ["greetings::greetings"]
                    self.cpp_info.components["helloworld"].libs = ["helloworld"]
                    self.cpp_info.components["worldall"].requires = ["helloworld",
                                                                     "greetings::greetings"]
                    self.cpp_info.components["worldall"].libs = ["worldall"]
            """)
        cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.0)
            project(world CXX)

            include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
            conan_basic_setup()

            find_package(greetings COMPONENTS hello)

            add_library(helloworld helloworld.cpp)
            target_link_libraries(helloworld greetings::greetings)

            find_package(greetings COMPONENTS bye)

            add_library(worldall worldall.cpp)
            target_link_libraries(worldall helloworld greetings::greetings)
            """)
        self._create_world(client, conanfile=conanfile, cmakelists=cmakelists)
        self.assertIn("Hello World!", client.out)
        self.assertIn("Bye World!", client.out)

    def component_not_found_test(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class GreetingsConan(ConanFile):
                def package_info(self):
                    self.cpp_info.components["hello"].libs = ["hello"]
        """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create . greetings/0.0.1@")

        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class WorldConan(ConanFile):
                requires = "greetings/0.0.1"

                def package_info(self):
                    self.cpp_info.components["helloworld"].requires = ["greetings::non-existent"]
                    self.cpp_info.components["helloworld"].libs = ["helloworld"]
        """)
        client.save({"conanfile.py": conanfile})
        client.run("create . world/0.0.1@")
        client.run("install world/0.0.1@ -g cmake_find_package", assert_error=True)
        self.assertIn("ERROR: Component 'greetings::non-existent' not found in 'greetings' "
                      "package requirement", client.out)

    def component_not_found_cmake_test(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class GreetingsConan(ConanFile):
                def package_info(self):
                    self.cpp_info.components["hello"].libs = ["hello"]
        """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create . greetings/0.0.1@")

        conanfile = textwrap.dedent("""
            from conans import ConanFile, CMake

            class ConsumerConan(ConanFile):
                generators = "cmake_find_package"
                requires = "greetings/0.0.1"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
        """)
        cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.0)
            project(Consumer CXX)

            find_package(greetings COMPONENTS hello)
            find_package(greetings COMPONENTS non-existent)
            """)
        client.save({"conanfile.py": conanfile, "CMakeLists.txt": cmakelists})
        client.run("install .")
        client.run("build .", assert_error=True)
        self.assertIn("Conan: Component 'hello' found in package 'greetings'", client.out)
        self.assertIn("Conan: Component 'non-existent' NOT found in package 'greetings'", client.out)

    def same_names_test(self):
        client = TestClient()
        conanfile_greetings = textwrap.dedent("""
            from conans import ConanFile, CMake

            class HelloConan(ConanFile):
                name = "hello"
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
                    self.copy("*.a", dst="lib", keep_path=False)

                def package_info(self):
                    self.cpp_info.components["global"].name = "hello"
                    self.cpp_info.components["global"].libs = ["hello"]
            """)
        hello_h = textwrap.dedent("""
            #pragma once
            void hello(std::string noun);
            """)

        hello_cpp = textwrap.dedent("""
            #include <iostream>
            #include <string>

            #include "hello.h"

            void hello(std::string noun) {
                std::cout << "Hello " << noun << "!" << std::endl;
            }
            """)
        cmakelists_greetings = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.0)
            project(greetings CXX)

            include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
            conan_basic_setup()

            add_library(hello hello.cpp)
            """)
        test_package_greetings_conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile, CMake

            class HelloTestConan(ConanFile):
                settings = "os", "compiler", "build_type", "arch"
                generators = "cmake", "cmake_find_package"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                    cmake.build()

                def test(self):
                    os.chdir("bin")
                    self.run(".%sexample" % os.sep)
            """)
        test_package_greetings_cpp = textwrap.dedent("""
            #include <string>

            #include "hello.h"

            int main() {
                hello("Moon");
            }
            """)
        test_package_greetings_cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.0)
            project(PackageTest CXX)

            include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
            conan_basic_setup()

            find_package(hello)

            add_executable(example example.cpp)
            target_link_libraries(example hello::hello)
            """)
        client.save({"conanfile.py": conanfile_greetings,
                     "src/CMakeLists.txt": cmakelists_greetings,
                     "src/hello.h": hello_h,
                     "src/hello.cpp": hello_cpp,
                     "test_package/conanfile.py": test_package_greetings_conanfile,
                     "test_package/example.cpp": test_package_greetings_cpp,
                     "test_package/CMakeLists.txt": test_package_greetings_cmakelists})
        client.run("create .")
        self.assertIn("Hello Moon!", client.out)

    def component_not_found_same_name_as_pkg_require_test(self):
        zlib = GenConanfile("zlib", "0.1").with_generator("cmake_find_package")
        mypkg = GenConanfile("mypkg", "0.1").with_generator("cmake_find_package")
        final = GenConanfile("final", "0.1").with_generator("cmake_find_package")\
            .with_require(ConanFileReference("zlib", "0.1", None, None))\
            .with_require(ConanFileReference("mypkg", "0.1", None, None))\
            .with_package_info(cpp_info={"components": {"cmp": {"requires": ["mypkg::zlib",
                                                                             "zlib::zlib"]}}},
                               env_info={})
        consumer = GenConanfile("consumer", "0.1").with_generator("cmake_find_package")\
            .with_requirement(ConanFileReference("final", "0.1", None, None))
        client = TestClient()
        client.save({"zlib.py": zlib, "mypkg.py": mypkg, "final.py": final, "consumer.py": consumer})
        client.run("create zlib.py")
        client.run("create mypkg.py")
        client.run("create final.py")
        client.run("install consumer.py", assert_error=True)
        self.assertIn("Component 'mypkg::zlib' not found in 'mypkg' package requirement", client.out)

    def filenames_test(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile, tools

            class HelloConan(ConanFile):
                name = "hello"
                version = "1.0"
                settings = "os", "compiler", "build_type", "arch"

                def package(self):
                    tools.save(os.path.join(self.package_folder, "lib", "hello.lib"), "")
                    tools.save(os.path.join(self.package_folder, "lib", "libhello.a"), "")

                def package_info(self):
                    self.cpp_info.names["cmake_find_package"] = "MYHELLO"
                    self.cpp_info.filenames["cmake_find_package"] = "hello_1"
                    self.cpp_info.components["1"].names["cmake_find_package"] = "HELLO1"
                    self.cpp_info.components["1"].libs = ["hello"]
        """)
        client.save({"conanfile.py": conanfile})
        client.run("create .")

        conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile, tools

            class HelloConan(ConanFile):
                name = "hello2"
                version = "1.0"
                settings = "os", "compiler", "build_type", "arch"
                requires = "hello/1.0"

                def package(self):
                    tools.save(os.path.join(self.package_folder, "lib", "hello2.lib"), "")
                    tools.save(os.path.join(self.package_folder, "lib", "libhello2.a"), "")

                def package_info(self):
                    self.cpp_info.names["cmake_find_package"] = "MYHELLO"
                    self.cpp_info.filenames["cmake_find_package"] = "hello_2"
                    self.cpp_info.components["1"].names["cmake_find_package"] = "HELLO2"
                    self.cpp_info.components["1"].libs = ["hello2"]
                    self.cpp_info.components["1"].requires = ["hello::1"]
        """)
        client.save({"conanfile.py": conanfile})
        client.run("create .")

        conanfile = textwrap.dedent("""
            from conans import ConanFile, CMake

            class Conan(ConanFile):
                requires = "hello2/1.0"
                generators = "cmake_find_package"
                settings = "os", "compiler", "build_type", "arch"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
            """)
        cmakelists = textwrap.dedent("""
            project(consumer)
            cmake_minimum_required(VERSION 3.1)
            find_package(hello_2)
            get_target_property(tmp MYHELLO::HELLO2 INTERFACE_LINK_LIBRARIES)
            message("Target libs (hello2): ${tmp}")
            get_target_property(tmp MYHELLO::HELLO1 INTERFACE_LINK_LIBRARIES)
            message("Target libs (hello): ${tmp}")
            """)
        client.save({"conanfile.py": conanfile, "CMakeLists.txt": cmakelists})
        client.run("install .")
        client.run("build .")

        self.assertIn('Library hello2 found', client.out)
        self.assertIn('Library hello found', client.out)
        self.assertIn("Target libs (hello2): "
                      "CONAN_LIB::MYHELLO_HELLO2_hello2;MYHELLO::HELLO1;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:>;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:>;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:>",
                      client.out)
        self.assertIn("Target libs (hello): "
                      "CONAN_LIB::MYHELLO_HELLO1_hello;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:>;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:>;"
                      "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:>",
                      client.out)
