import platform
import textwrap
import unittest

import pytest

from conans.model.ref import ConanFileReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.assets.sources import gen_function_h, gen_function_cpp
from conans.test.utils.tools import TestClient


@pytest.fixture(scope="module")
def create_greetings():
    """
    creates a multi-component package with 2 components "hello" and "bye
    """
    hello_h = gen_function_h(name="hello")
    hello_cpp = gen_function_cpp(name="hello", includes=["hello"])
    bye_h = gen_function_h(name="bye")
    bye_cpp = gen_function_cpp(name="bye", includes=["bye"])

    conanfile_greetings = textwrap.dedent("""
        from conans import ConanFile, CMake

        class GreetingsConan(ConanFile):
            name = "greetings"
            version = "0.0.1"
            settings = "os", "compiler", "build_type", "arch"
            generators = "cmake"
            exports_sources = "src/*"
            options = {"components": ["standard", "custom", "none"]}
            default_options = {"components": "standard"}

            def build(self):
                cmake = CMake(self)
                cmake.configure(source_folder="src")
                cmake.build()

            def package(self):
                self.copy("*.h", dst="include", src="src")
                self.copy("*.lib", dst="lib", keep_path=False)
                self.copy("*.a", dst="lib", keep_path=False)

            def package_info(self):
                if self.options.components == "standard":
                    self.cpp_info.components["hello"].libs = ["hello"]
                    self.cpp_info.components["bye"].libs = ["bye"]
                elif self.options.components == "custom":
                    self.cpp_info.names["cmake_find_package_multi"] = "MyGreetings"
                    self.cpp_info.components["hello"].names["cmake_find_package_multi"] = "MyHello"
                    self.cpp_info.components["bye"].names["cmake_find_package_multi"] = "MyBye"
                else:
                    self.cpp_info.libs = ["hello", "bye"]

            def package_id(self):
                del self.info.options.components
        """)

    cmakelists_greetings = textwrap.dedent("""
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
        cmake_minimum_required(VERSION 3.0)
        project(greetings CXX)

        include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
        conan_output_dirs_setup()

        add_library(hello hello.cpp)
        add_library(bye bye.cpp)
        """)

    test_package_greetings_conanfile = textwrap.dedent("""
        import os
        from conans import ConanFile, CMake

        class GreetingsTestConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "cmake", "cmake_find_package_multi"
            requires = "greetings/0.0.1"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def test(self):
                os.chdir("bin")
                self.run(".%sexample" % os.sep)
        """)
    test_package_greetings_cpp = gen_function_cpp(name="main", includes=["hello", "bye"],
                                                  calls=["hello", "bye"])

    test_package_greetings_cmakelists = textwrap.dedent("""
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
        cmake_minimum_required(VERSION 3.0)
        project(PackageTest CXX)

        include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
        conan_output_dirs_setup()

        find_package(greetings)

        add_executable(example example.cpp)
        target_link_libraries(example greetings::greetings)
        """)

    client = TestClient()
    client.save({"conanfile.py": conanfile_greetings,
                 "src/CMakeLists.txt": cmakelists_greetings,
                 "src/hello.h": hello_h,
                 "src/hello.cpp": hello_cpp,
                 "src/bye.h": bye_h,
                 "src/bye.cpp": bye_cpp,
                 "test_package/conanfile.py": test_package_greetings_conanfile,
                 "test_package/example.cpp": test_package_greetings_cpp,
                 "test_package/CMakeLists.txt": test_package_greetings_cmakelists})
    client.run("create . -s build_type=Release")
    assert "hello: Release!" in client.out
    assert "bye: Release!" in client.out
    client.run("create . -s build_type=Debug")
    assert "hello: Debug!" in client.out
    assert "bye: Debug!" in client.out
    return client


def test_basic(create_greetings):
    client = create_greetings

    conanfile = textwrap.dedent("""
        from conans import ConanFile, CMake

        class Chat(ConanFile):
            name = "chat"
            version = "0.0.1"
            settings = "os", "compiler", "build_type", "arch"
            generators = "cmake_find_package_multi", "cmake"
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
                self.cpp_info.components["sayhello"].requires = ["greetings::hello"]
                self.cpp_info.components["sayhello"].libs = ["sayhello"]
                self.cpp_info.components["sayhellobye"].requires = ["sayhello",
                                                                    "greetings::greetings"]
                self.cpp_info.components["sayhellobye"].libs = ["sayhellobye"]
        """)
    sayhello_h = gen_function_h(name="sayhello")
    sayhello_cpp = gen_function_cpp(name="sayhello", includes=["hello"], calls=["hello"])
    sayhellobye_h = gen_function_h(name="sayhellobye")
    sayhellobye_cpp = gen_function_cpp(name="sayhellobye", includes=["sayhello", "bye"],
                                       calls=["sayhello", "bye"])

    cmakelists = textwrap.dedent("""
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
        cmake_minimum_required(VERSION 3.0)
        project(world CXX)

        include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
        conan_output_dirs_setup()

        find_package(greetings COMPONENTS hello bye)

        add_library(sayhello sayhello.cpp)
        target_link_libraries(sayhello greetings::hello)

        add_library(sayhellobye sayhellobye.cpp)
        target_link_libraries(sayhellobye sayhello greetings::bye)
        """)
    test_conanfile = textwrap.dedent("""
        import os
        from conans import ConanFile, CMake

        class WorldTestConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "cmake", "cmake_find_package_multi"
            requires = "chat/0.0.1"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def test(self):
                os.chdir("bin")
                self.run(".%sexample" % os.sep)
                self.run(".%sexample2" % os.sep)
        """)
    test_example_cpp = gen_function_cpp(name="main", includes=["sayhellobye"], calls=["sayhellobye"])

    test_cmakelists = textwrap.dedent("""
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
        cmake_minimum_required(VERSION 3.0)
        project(PackageTest CXX)

        include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
        conan_output_dirs_setup()

        # necessary for the local
        set(CMAKE_MODULE_PATH ${CMAKE_BINARY_DIR} ${CMAKE_MODULE_PATH})
        set(CMAKE_PREFIX_PATH ${CMAKE_BINARY_DIR} ${CMAKE_PREFIX_PATH})
        find_package(chat)

        add_executable(example example.cpp)
        target_link_libraries(example chat::sayhellobye)

        add_executable(example2 example.cpp)
        target_link_libraries(example2 chat::chat)
        """)
    client.save({"conanfile.py": conanfile,
                 "src/CMakeLists.txt": cmakelists,
                 "src/sayhello.h": sayhello_h,
                 "src/sayhello.cpp": sayhello_cpp,
                 "src/sayhellobye.h": sayhellobye_h,
                 "src/sayhellobye.cpp": sayhellobye_cpp,
                 "test_package/conanfile.py": test_conanfile,
                 "test_package/CMakeLists.txt": test_cmakelists,
                 "test_package/example.cpp": test_example_cpp}, clean_first=True)
    client.run("create . -s build_type=Release")
    assert "sayhellobye: Release!" in client.out
    assert "sayhello: Release!" in client.out
    assert "hello: Release!" in client.out
    assert "bye: Release!" in client.out
    client.run("create . -s build_type=Debug")
    assert "sayhellobye: Debug!" in client.out
    assert "sayhello: Debug!" in client.out
    assert "hello: Debug!" in client.out
    assert "bye: Debug!" in client.out

    # Test consumer multi-config
    if platform.system() == "Windows":
        with client.chdir("test_package"):
            client.run("install . -s build_type=Release")
            client.run("install . -s build_type=Debug")
            client.run_command('cmake . ')
            client.run_command("cmake --build . --config Debug")
            client.run_command(r".\bin\example.exe")
            assert "sayhellobye: Debug!" in client.out
            assert "sayhello: Debug!" in client.out
            assert "hello: Debug!" in client.out
            assert "bye: Debug!" in client.out
            client.run_command("cmake --build . --config Release")
            client.run_command(r".\bin\example.exe")
            assert "sayhellobye: Release!" in client.out
            assert "sayhello: Release!" in client.out
            assert "hello: Release!" in client.out
            assert "bye: Release!" in client.out


def test_custom_names(create_greetings):
    client = create_greetings

    conanfile = textwrap.dedent("""
        from conans import ConanFile, CMake

        class Chat(ConanFile):
            name = "chat"
            version = "0.0.1"
            settings = "os", "compiler", "build_type", "arch"
            generators = "cmake_find_package_multi", "cmake"
            exports_sources = "src/*"
            requires = "greetings/0.0.1"
            default_options = {"greetings:components": "custom"}

            def build(self):
                cmake = CMake(self)
                cmake.configure(source_folder="src")
                cmake.build()

            def package(self):
                self.copy("*.h", dst="include", src="src")
                self.copy("*.lib", dst="lib", keep_path=False)
                self.copy("*.a", dst="lib", keep_path=False)

            def package_info(self):
                self.cpp_info.names["cmake_find_package_multi"] = "MyChat"
                self.cpp_info.components["sayhello"].names["cmake_find_package_multi"] = "MySay"
                self.cpp_info.components["sayhello"].requires = ["greetings::hello"]
                self.cpp_info.components["sayhello"].libs = ["sayhello"]
                self.cpp_info.components["sayhellobye"].names["cmake_find_package_multi"] ="MySayBye"
                self.cpp_info.components["sayhellobye"].requires = ["sayhello", "greetings::bye"]
                self.cpp_info.components["sayhellobye"].libs = ["sayhellobye"]
        """)
    sayhello_h = gen_function_h(name="sayhello")
    sayhello_cpp = gen_function_cpp(name="sayhello", includes=["hello"], calls=["hello"])
    sayhellobye_h = gen_function_h(name="sayhellobye")
    sayhellobye_cpp = gen_function_cpp(name="sayhellobye", includes=["sayhello", "bye"],
                                       calls=["sayhello", "bye"])

    cmakelists = textwrap.dedent("""
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
        cmake_minimum_required(VERSION 3.0)
        project(world CXX)

        include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
        conan_output_dirs_setup()

        find_package(MyGreetings COMPONENTS MyHello MyBye)

        add_library(sayhello sayhello.cpp)
        target_link_libraries(sayhello MyGreetings::MyHello)

        add_library(sayhellobye sayhellobye.cpp)
        target_link_libraries(sayhellobye sayhello MyGreetings::MyBye)
        """)
    test_conanfile = textwrap.dedent("""
        import os
        from conans import ConanFile, CMake

        class WorldTestConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "cmake", "cmake_find_package_multi"
            requires = "chat/0.0.1"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def test(self):
                os.chdir("bin")
                self.run(".%sexample" % os.sep)
                self.run(".%sexample2" % os.sep)
        """)
    test_example_cpp = gen_function_cpp(name="main", includes=["sayhellobye"], calls=["sayhellobye"])

    test_cmakelists = textwrap.dedent("""
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
        cmake_minimum_required(VERSION 3.0)
        project(PackageTest CXX)

        include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
        conan_output_dirs_setup()

        # necessary for the local
        set(CMAKE_MODULE_PATH ${CMAKE_BINARY_DIR} ${CMAKE_MODULE_PATH})
        set(CMAKE_PREFIX_PATH ${CMAKE_BINARY_DIR} ${CMAKE_PREFIX_PATH})
        find_package(MyChat)

        add_executable(example example.cpp)
        target_link_libraries(example MyChat::MySayBye)

        add_executable(example2 example.cpp)
        target_link_libraries(example2 MyChat::MyChat)
        """)
    client.save({"conanfile.py": conanfile,
                 "src/CMakeLists.txt": cmakelists,
                 "src/sayhello.h": sayhello_h,
                 "src/sayhello.cpp": sayhello_cpp,
                 "src/sayhellobye.h": sayhellobye_h,
                 "src/sayhellobye.cpp": sayhellobye_cpp,
                 "test_package/conanfile.py": test_conanfile,
                 "test_package/CMakeLists.txt": test_cmakelists,
                 "test_package/example.cpp": test_example_cpp}, clean_first=True)
    client.run("create . -s build_type=Release")
    assert "sayhellobye: Release!" in client.out
    assert "sayhello: Release!" in client.out
    assert "hello: Release!" in client.out
    assert "bye: Release!" in client.out
    client.run("create . -s build_type=Debug")
    assert "sayhellobye: Debug!" in client.out
    assert "sayhello: Debug!" in client.out
    assert "hello: Debug!" in client.out
    assert "bye: Debug!" in client.out


@pytest.mark.slow
@pytest.mark.tool_cmake
class CMakeGeneratorsWithComponentsTest(unittest.TestCase):


    def test_find_package_general(self):
        client = TestClient()
        self._create_greetings(client, custom_names=True)

        conanfile = textwrap.dedent("""
            from conans import ConanFile, CMake

            class WorldConan(ConanFile):
                name = "world"
                version = "0.0.1"
                settings = "os", "compiler", "build_type", "arch"
                generators = "cmake", "cmake_find_package_multi"
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
                    self.cpp_info.names["cmake_find_package_multi"] = "World"
                    self.cpp_info.components["helloworld"].names["cmake_find_package_multi"] = "Helloworld"
                    self.cpp_info.components["helloworld"].requires = ["greetings::hello"]
                    self.cpp_info.components["helloworld"].libs = ["Helloworld"]
                    self.cpp_info.components["worldall"].names["cmake_find_package_multi"] = "Worldall"
                    self.cpp_info.components["worldall"].requires = ["greetings::bye", "helloworld"]
                    self.cpp_info.components["worldall"].libs = ["Worldall"]
        """)
        cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.0)
            project(world CXX)

            include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
            conan_basic_setup(NO_OUTPUT_DIRS)
            set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/${CMAKE_BUILD_TYPE})

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
            conan_basic_setup(NO_OUTPUT_DIRS)
            set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/${CMAKE_BUILD_TYPE})

            find_package(World)

            add_executable(example example.cpp)
            target_link_libraries(example World::Worldall)

            add_executable(example2 example.cpp)
            target_link_libraries(example2 World::World)
            """)
        self._create_world(client, conanfile=conanfile, cmakelists=cmakelists,
                           test_cmakelists=test_cmakelists)
        self._install_build_run_test_package(client, "Release", run_example2=True)
        self.assertIn("Hello World release!", client.out)
        self.assertIn("Bye World release!", client.out)
        self._install_build_run_test_package(client, "Debug", run_example2=True)
        self.assertIn("Hello World debug!", client.out)
        self.assertIn("Bye World debug!", client.out)

    def test_recipe_with_components_requiring_recipe_without_components(self):
        client = TestClient()
        self._create_greetings(client, components=False)

        conanfile = textwrap.dedent("""
            from conans import ConanFile, CMake

            class WorldConan(ConanFile):
                name = "world"
                version = "0.0.1"
                settings = "os", "compiler", "build_type", "arch"
                generators = "cmake_find_package_multi", "cmake"
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
            conan_basic_setup(NO_OUTPUT_DIRS)
            set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/${CMAKE_BUILD_TYPE})

            find_package(greetings COMPONENTS hello)

            add_library(helloworld helloworld.cpp)
            target_link_libraries(helloworld greetings::greetings)

            find_package(greetings COMPONENTS bye)

            add_library(worldall worldall.cpp)
            target_link_libraries(worldall helloworld greetings::greetings)
            """)
        self._create_world(client, conanfile=conanfile, cmakelists=cmakelists)
        self._install_build_run_test_package(client, "Release", run_example2=True)
        self.assertIn("Hello World release!", client.out)
        self.assertIn("Bye World release!", client.out)
        self._install_build_run_test_package(client, "Debug", run_example2=True)
        self.assertIn("Hello World debug!", client.out)
        self.assertIn("Bye World debug!", client.out)

    def test_component_not_found(self):
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
        client.run("install world/0.0.1@ -g cmake_find_package_multi", assert_error=True)
        self.assertIn("ERROR: Component 'greetings::non-existent' not found in 'greetings' "
                      "package requirement", client.out)

    def test_component_not_found_cmake(self):
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
                settings = "build_type"
                generators = "cmake_find_package_multi"
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

    def test_same_names(self):
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
                generators = "cmake", "cmake_find_package_multi"

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

    def test_component_not_found_same_name_as_pkg_require(self):
        zlib = GenConanfile("zlib", "0.1").with_setting("build_type")\
            .with_generator("cmake_find_package_multi")
        mypkg = GenConanfile("mypkg", "0.1").with_setting("build_type")\
            .with_generator("cmake_find_package_multi")
        final = GenConanfile("final", "0.1").with_setting("build_type")\
            .with_generator("cmake_find_package_multi")\
            .with_require(ConanFileReference("zlib", "0.1", None, None))\
            .with_require(ConanFileReference("mypkg", "0.1", None, None))\
            .with_package_info(cpp_info={"components": {"cmp": {"requires": ["mypkg::zlib",
                                                                             "zlib::zlib"]}}},
                               env_info={})
        consumer = GenConanfile("consumer", "0.1").with_setting("build_type")\
            .with_generator("cmake_find_package_multi")\
            .with_requirement(ConanFileReference("final", "0.1", None, None))
        client = TestClient()
        client.save({"zlib.py": zlib, "mypkg.py": mypkg, "final.py": final, "consumer.py": consumer})
        client.run("create zlib.py")
        client.run("create mypkg.py")
        client.run("create final.py")
        client.run("install consumer.py", assert_error=True)
        self.assertIn("Component 'mypkg::zlib' not found in 'mypkg' package requirement", client.out)

    def test_filenames(self):
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
                    self.cpp_info.names["cmake_find_package_multi"] = "MYHELLO"
                    self.cpp_info.filenames["cmake_find_package_multi"] = "hello_1"
                    self.cpp_info.components["1"].names["cmake_find_package_multi"] = "HELLO1"
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
                    self.cpp_info.names["cmake_find_package_multi"] = "MYHELLO"
                    self.cpp_info.filenames["cmake_find_package_multi"] = "hello_2"
                    self.cpp_info.components["1"].names["cmake_find_package_multi"] = "HELLO2"
                    self.cpp_info.components["1"].libs = ["hello2"]
                    self.cpp_info.components["1"].requires = ["hello::1"]
        """)
        client.save({"conanfile.py": conanfile})
        client.run("create .")

        conanfile = textwrap.dedent("""
            from conans import ConanFile, CMake

            class Conan(ConanFile):
                requires = "hello2/1.0"
                generators = "cmake_find_package_multi"
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

        assert ("Target libs (hello2): "
                "$<$<CONFIG:Debug>:;>;"
                "$<$<CONFIG:Release>:CONAN_LIB::MYHELLO_HELLO2_hello2RELEASE;MYHELLO::HELLO1;"
                "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:>;"
                "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:>;"
                "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:>>;"
                "$<$<CONFIG:RelWithDebInfo>:;>;$<$<CONFIG:MinSizeRel>:;>") in client.out

        assert ("Target libs (hello): "
                "$<$<CONFIG:Debug>:;>;"
                "$<$<CONFIG:Release>:CONAN_LIB::MYHELLO_HELLO1_helloRELEASE;"
                "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:>;"
                "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:>;"
                "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:>>;"
                "$<$<CONFIG:RelWithDebInfo>:;>;$<$<CONFIG:MinSizeRel>:;>") in client.out

    def test_same_name_global_target_collision(self):
        # https://github.com/conan-io/conan/issues/7889
        conanfile_tpl = textwrap.dedent("""
            import os
            from conans import ConanFile, CMake

            class Conan(ConanFile):
                name = "{name}"
                version = "1.0"
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
                    self.cpp_info.names["cmake_find_package_multi"] = "nonstd"
                    self.cpp_info.filenames["cmake_find_package_multi"] = "{name}"
                    self.cpp_info.components["1"].names["cmake_find_package_multi"] = "{name}"
                    self.cpp_info.components["1"].libs = ["{name}"]
            """)
        client = TestClient()
        for name in ["expected", "variant"]:
            client.run("new {name}/1.0 -s".format(name=name))
            client.save({"conanfile.py": conanfile_tpl.format(name=name)})
            client.run("create . {name}/1.0@".format(name=name))
        middle_cmakelists = textwrap.dedent("""
            project(middle)
            cmake_minimum_required(VERSION 3.1)

            include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
            conan_basic_setup()

            find_package(expected)
            find_package(variant)

            add_library(middle middle.cpp)
            target_link_libraries(middle nonstd::nonstd)
            """)
        middle_h = gen_function_h(name="middle")
        middle_cpp = textwrap.dedent("""
            #include "middle.h"
            #include "expected.h"
            #include "variant.h"

            int middle() {
                expected();
                variant();
                return 0;
            }
            """)
        middle_conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile, CMake

            class Conan(ConanFile):
                name = "middle"
                version = "1.0"
                settings = "os", "compiler", "build_type", "arch"
                generators = "cmake", "cmake_find_package_multi"
                exports_sources = "src/*"
                requires = "expected/1.0", "variant/1.0"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure(source_folder="src")
                    cmake.build()

                def package(self):
                    self.copy("*.h", dst="include", src="src")
                    self.copy("*.lib", dst="lib", keep_path=False)
                    self.copy("*.a", dst="lib", keep_path=False)

                def package_info(self):
                    self.cpp_info.libs = ["middle"]
            """)
        client.save({"conanfile.py": middle_conanfile, "src/CMakeLists.txt": middle_cmakelists,
                     "src/middle.h": middle_h, "src/middle.cpp": middle_cpp}, clean_first=True)
        client.run("create . middle/1.0@")
        conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile, CMake

            class Conan(ConanFile):
                name = "consumer"
                version = "1.0"
                generators = "cmake_find_package_multi", "cmake"
                settings = "os", "compiler", "build_type", "arch"
                exports_sources = "src/*"
                requires = "middle/1.0"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure(source_folder="src")
                    cmake.build()
                    self.run(os.path.join("bin", "main"))
            """)
        cmakelists = textwrap.dedent("""
            project(consumer)
            cmake_minimum_required(VERSION 3.1)

            include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
            conan_basic_setup()

            find_package(middle)

            get_target_property(tmp middle::middle INTERFACE_LINK_LIBRARIES)
            message("Middle link libraries: ${tmp}")

            add_executable(main main.cpp)
            target_link_libraries(main middle::middle)
            """)
        main_cpp = textwrap.dedent("""
            #include "middle.h"

            int main() {
                middle();
            }
            """)
        client.save({"conanfile.py": conanfile,
                     "src/CMakeLists.txt": cmakelists,
                     "src/main.cpp": main_cpp}, clean_first=True)
        client.run("create . consumer/1.0@")
        self.assertIn('Library middle found', client.out)
        self.assertIn('Library expected found', client.out)
        self.assertIn('Library variant found', client.out)
        assert ("Middle link libraries: "
                "$<$<CONFIG:Debug>:;>;"
                "$<$<CONFIG:Release>:CONAN_LIB::middle_middle_RELEASE;nonstd::nonstd;"
                "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:>;"
                "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:>;"
                "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:>>;"
                "$<$<CONFIG:RelWithDebInfo>:;>;$<$<CONFIG:MinSizeRel>:;>") in client.out
        self.assertIn('expected/1.0: Hello World Release!', client.out)
        self.assertIn('variant/1.0: Hello World Release!', client.out)
