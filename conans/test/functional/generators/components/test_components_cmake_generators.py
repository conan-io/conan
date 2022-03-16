import platform
import textwrap

import pytest

from conans.model.ref import ConanFileReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.assets.sources import gen_function_h, gen_function_cpp
from conans.test.utils.tools import TestClient


@pytest.mark.slow
@pytest.mark.tool_cmake
@pytest.fixture(scope="module")
def setup_client_with_greetings():
    """
    creates a multi-component package with 2 components "hello" and "bye
    """
    hello_h = gen_function_h(name="hello")
    hello_cpp = gen_function_cpp(name="hello", includes=["hello"])
    bye_h = gen_function_h(name="bye")
    bye_cpp = gen_function_cpp(name="bye", includes=["bye"])

    conanfile_greetings = textwrap.dedent("""
        import os
        from conans import ConanFile, CMake, tools

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
                tools.save(os.path.join(self.package_folder,
                                        "my_cmake_functions.cmake"), "set(MY_CMAKE_VAR 99)")

            def package_info(self):

                if self.options.components == "standard":
                    self.cpp_info.components["hello"].libs = ["hello"]
                    self.cpp_info.components["bye"].libs = ["bye"]
                    self.cpp_info.components["hello"].build_modules = ["my_cmake_functions.cmake"]
                elif self.options.components == "custom":
                    self.cpp_info.filenames["cmake_find_package_multi"] = "MYG"
                    self.cpp_info.filenames["cmake_find_package"] = "MYG"
                    self.cpp_info.set_property("cmake_file_name", "MYG")

                    self.cpp_info.names["cmake_find_package_multi"] = "MyGreetings"
                    self.cpp_info.names["cmake_find_package"] = "MyGreetings"
                    self.cpp_info.set_property("cmake_target_name", "MyGreetings")

                    self.cpp_info.components["hello"].names["cmake_find_package_multi"] = "MyHello"
                    self.cpp_info.components["bye"].names["cmake_find_package_multi"] = "MyBye"
                    self.cpp_info.components["hello"].names["cmake_find_package"] = "MyHello"
                    self.cpp_info.components["bye"].names["cmake_find_package"] = "MyBye"
                    self.cpp_info.components["hello"].set_property("cmake_target_name", "MyHello")
                    self.cpp_info.components["bye"].set_property("cmake_target_name", "MyBye")

                    self.cpp_info.components["hello"].libs = ["hello"]
                    self.cpp_info.components["bye"].libs = ["bye"]

                    # Duplicated on purpose to check that it doesn't break
                    self.cpp_info.components["bye"].build_modules = ["my_cmake_functions.cmake"]
                    self.cpp_info.components["hello"].build_modules = ["my_cmake_functions.cmake"]

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


def create_chat(client, generator, components, package_info, cmake_find, test_cmake_find):
    conanfile = textwrap.dedent("""
        from conans import ConanFile, CMake

        class Chat(ConanFile):
            name = "chat"
            version = "0.0.1"
            settings = "os", "compiler", "build_type", "arch"
            generators = "{}", "cmake"
            exports_sources = "src/*"
            requires = "greetings/0.0.1"
            default_options = {{"greetings/*:components": "{}"}}

            def build(self):
                cmake = CMake(self)
                cmake.configure(source_folder="src")
                cmake.build()

            def package(self):
                self.copy("*.h", dst="include", src="src")
                self.copy("*.lib", dst="lib", keep_path=False)
                self.copy("*.a", dst="lib", keep_path=False)

            def package_info(self):
                {}
        """).format(generator, components, "\n        ".join(package_info.splitlines()))
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

        %s
        """ % cmake_find)

    test_conanfile = textwrap.dedent("""
        import os
        from conans import ConanFile, CMake

        class WorldTestConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "cmake", "{}"
            requires = "chat/0.0.1"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def test(self):
                os.chdir("bin")
                self.run(".%sexample" % os.sep)
                self.run(".%sexample2" % os.sep)
        """.format(generator))
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
        %s
        """ % test_cmake_find)
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


@pytest.mark.parametrize("generator", ["cmake_find_package_multi", "cmake_find_package"])
def test_standard_names(setup_client_with_greetings, generator):
    client = setup_client_with_greetings

    package_info = textwrap.dedent("""
        self.cpp_info.components["sayhello"].requires = ["greetings::hello"]
        self.cpp_info.components["sayhello"].libs = ["sayhello"]
        self.cpp_info.components["sayhellobye"].requires = ["sayhello", "greetings::bye"]
        self.cpp_info.components["sayhellobye"].libs = ["sayhellobye"]
        """)
    cmake_find = textwrap.dedent("""
        find_package(greetings COMPONENTS hello bye)

        add_library(sayhello sayhello.cpp)
        target_link_libraries(sayhello greetings::hello)

        add_library(sayhellobye sayhellobye.cpp)
        target_link_libraries(sayhellobye sayhello greetings::bye)
        """)
    test_cmake_find = textwrap.dedent("""
        find_package(chat)

        add_executable(example example.cpp)
        target_link_libraries(example chat::sayhellobye)

        add_executable(example2 example.cpp)
        target_link_libraries(example2 chat::chat)
        """)

    create_chat(client, generator, "standard", package_info, cmake_find, test_cmake_find)

    # Test consumer multi-config
    if generator == "cmake_find_package_multi" and platform.system() == "Windows":
        with client.chdir("test_package"):
            client.run("install . -s build_type=Release")
            client.run("install . -s build_type=Debug")
            client.run_command('cmake . -G "Visual Studio 15 Win64"')
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


@pytest.mark.parametrize("generator", ["cmake_find_package_multi", "cmake_find_package"])
def test_custom_names(setup_client_with_greetings, generator):
    client = setup_client_with_greetings

    package_info = textwrap.dedent("""
        self.cpp_info.names["cmake_find_package_multi"] = "MyChat"
        self.cpp_info.names["cmake_find_package"] = "MyChat"
        # NOTE: For the new CMakeDeps only filenames mean filename, it is not using the "names" field
        self.cpp_info.set_property("cmake_target_name", "MyChat")
        self.cpp_info.set_property("cmake_file_name", "MyChat")

        self.cpp_info.components["sayhello"].names["cmake_find_package_multi"] = "MySay"
        self.cpp_info.components["sayhello"].names["cmake_find_package"] = "MySay"
        self.cpp_info.components["sayhello"].set_property("cmake_target_name", "MySay")

        self.cpp_info.components["sayhello"].requires = ["greetings::hello"]
        self.cpp_info.components["sayhello"].libs = ["sayhello"]
        self.cpp_info.components["sayhellobye"].names["cmake_find_package_multi"] ="MySayBye"
        self.cpp_info.components["sayhellobye"].names["cmake_find_package"] ="MySayBye"
        self.cpp_info.components["sayhellobye"].set_property("cmake_target_name", "MySayBye")

        self.cpp_info.components["sayhellobye"].requires = ["sayhello", "greetings::bye"]
        self.cpp_info.components["sayhellobye"].libs = ["sayhellobye"]
        """)

    cmake_find = textwrap.dedent("""
        find_package(MYG COMPONENTS MyHello MyBye)

        add_library(sayhello sayhello.cpp)
        target_link_libraries(sayhello MyGreetings::MyHello)

        add_library(sayhellobye sayhellobye.cpp)
        target_link_libraries(sayhellobye sayhello MyGreetings::MyBye)
        """)

    test_cmake_find = textwrap.dedent("""
        find_package(MyChat)

        add_executable(example example.cpp)
        target_link_libraries(example MyChat::MySayBye)

        add_executable(example2 example.cpp)
        target_link_libraries(example2 MyChat::MyChat)
        """)
    create_chat(client, generator, "custom", package_info, cmake_find, test_cmake_find)


@pytest.mark.parametrize("generator", ["cmake_find_package_multi", "cmake_find_package"])
def test_no_components(setup_client_with_greetings, generator):
    client = setup_client_with_greetings

    package_info = textwrap.dedent("""
        self.cpp_info.components["sayhello"].requires = ["greetings::greetings"]
        self.cpp_info.components["sayhello"].libs = ["sayhello"]
        self.cpp_info.components["sayhellobye"].requires = ["sayhello", "greetings::greetings"]
        self.cpp_info.components["sayhellobye"].libs = ["sayhellobye"]
        """)

    cmake_find = textwrap.dedent("""
        find_package(greetings)

        add_library(sayhello sayhello.cpp)
        target_link_libraries(sayhello greetings::greetings)

        add_library(sayhellobye sayhellobye.cpp)
        target_link_libraries(sayhellobye sayhello greetings::greetings)
        """)

    test_cmake_find = textwrap.dedent("""
        find_package(chat)

        add_executable(example example.cpp)
        target_link_libraries(example chat::sayhellobye)

        add_executable(example2 example.cpp)
        target_link_libraries(example2 chat::chat)
        """)
    create_chat(client, generator, "none", package_info, cmake_find, test_cmake_find)


@pytest.mark.parametrize("generator", ["cmake_find_package_multi", "cmake_find_package"])
@pytest.mark.slow
@pytest.mark.tool_cmake
def test_same_names(generator):
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
    hello_h = gen_function_h(name="hello")
    hello_cpp = gen_function_cpp(name="hello", includes=["hello"])

    cmakelists_greetings = textwrap.dedent("""
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
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
            generators = "cmake", "{}"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def test(self):
                os.chdir("bin")
                self.run(".%sexample" % os.sep)
        """.format(generator))
    test_package_greetings_cpp = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])

    test_package_greetings_cmakelists = textwrap.dedent("""
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
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
    assert "hello: Release!" in client.out


@pytest.mark.tool_cmake
class TestComponentsCMakeGenerators:

    @pytest.mark.parametrize("generator", ["cmake_find_package_multi", "cmake_find_package"])
    def test_component_not_found(self, generator):
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
        client.run("install world/0.0.1@ -g {}".format(generator), assert_error=True)
        assert ("Component 'greetings::non-existent' not found in 'greetings' "
                "package requirement" in client.out)

    @pytest.mark.parametrize("generator, filename", [("cmake_find_package_multi", "greetings"),
                                                     ("cmake_find_package_multi", "filegreetings"),
                                                     ("cmake_find_package", "greetings"),
                                                     ("cmake_find_package", "filegreetings")])
    def test_component_not_found_cmake(self, generator, filename):
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class GreetingsConan(ConanFile):
                def package_info(self):
                    self.cpp_info.components["hello"].libs = ["hello"]
                    self.cpp_info.filenames["{}"] = "{}"
        """.format(generator, filename))
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create . greetings/0.0.1@")

        conanfile = textwrap.dedent("""
            from conans import ConanFile, CMake

            class ConsumerConan(ConanFile):
                settings = "build_type"
                generators = "{}"
                requires = "greetings/0.0.1"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
        """.format(generator))
        cmakelists = textwrap.dedent("""
            set(CMAKE_CXX_COMPILER_WORKS 1)
            set(CMAKE_CXX_ABI_COMPILED 1)
            cmake_minimum_required(VERSION 3.0)
            project(Consumer CXX)

            find_package({filename} COMPONENTS hello)
            find_package({filename} COMPONENTS non-existent)
            """.format(filename=filename))
        client.save({"conanfile.py": conanfile, "CMakeLists.txt": cmakelists})
        client.run("install .")
        client.run("build .", assert_error=True)
        assert "Conan: Component 'hello' found in package 'greetings'" in client.out
        assert "Conan: Component 'non-existent' NOT found in package 'greetings'" in client.out

    @pytest.mark.parametrize("generator", ["cmake_find_package_multi", "cmake_find_package"])
    def test_component_not_found_same_name_as_pkg_require(self, generator):
        zlib = GenConanfile("zlib", "0.1").with_setting("build_type").with_generator(generator)
        mypkg = GenConanfile("mypkg", "0.1").with_setting("build_type").with_generator(generator)
        final = GenConanfile("final", "0.1").with_setting("build_type").with_generator(generator)\
            .with_require(ConanFileReference("zlib", "0.1", None, None))\
            .with_require(ConanFileReference("mypkg", "0.1", None, None))\
            .with_package_info(cpp_info={"components": {"cmp": {"requires": ["mypkg::zlib",
                                                                             "zlib::zlib"]}}},
                               env_info={})
        consumer = GenConanfile("consumer", "0.1").with_setting("build_type")\
            .with_generator(generator)\
            .with_requirement(ConanFileReference("final", "0.1", None, None))
        client = TestClient()
        client.save({"zlib.py": zlib, "mypkg.py": mypkg, "final.py": final, "consumer.py": consumer})
        client.run("create zlib.py")
        client.run("create mypkg.py")
        client.run("create final.py")
        client.run("install consumer.py", assert_error=True)
        assert "Component 'mypkg::zlib' not found in 'mypkg' package requirement" in client.out

    @pytest.mark.slow
    @pytest.mark.parametrize("generator", ["cmake_find_package_multi", "cmake_find_package"])
    def test_same_name_global_target_collision(self, generator):
        # https://github.com/conan-io/conan/issues/7889
        conanfile_tpl = textwrap.dedent("""
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
                    self.cpp_info.names["{generator}"] = "nonstd"
                    self.cpp_info.filenames["{generator}"] = "{name}"
                    self.cpp_info.set_property("cmake_target_name", "nonstd")
                    self.cpp_info.set_property("cmake_file_name", "{name}")

                    self.cpp_info.components["1"].names["{generator}"] = "{name}"
                    self.cpp_info.components["1"].set_property("cmake_target_name", "{name}")
                    self.cpp_info.components["1"].libs = ["{name}"]
            """)
        client = TestClient()
        for name in ["expected", "variant"]:
            client.run("new {name}/1.0 -s".format(name=name))
            client.save({"conanfile.py": conanfile_tpl.format(name=name, generator=generator)})
            client.run("create . {name}/1.0@".format(name=name))
        middle_cmakelists = textwrap.dedent("""
            set(CMAKE_CXX_COMPILER_WORKS 1)
            set(CMAKE_CXX_ABI_COMPILED 1)
            project(middle CXX)
            cmake_minimum_required(VERSION 3.1)

            include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
            conan_basic_setup()

            find_package(expected)
            find_package(variant)

            add_library(middle middle.cpp)
            target_link_libraries(middle nonstd::nonstd)
            """)
        middle_h = gen_function_h(name="middle")
        middle_cpp = gen_function_cpp(name="middle", includes=["middle", "expected", "variant"],
                                      calls=["expected", "variant"])
        middle_conanfile = textwrap.dedent("""
            from conans import ConanFile, CMake

            class Conan(ConanFile):
                name = "middle"
                version = "1.0"
                settings = "os", "compiler", "build_type", "arch"
                generators = "cmake", "{}"
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
            """.format(generator))
        client.save({"conanfile.py": middle_conanfile, "src/CMakeLists.txt": middle_cmakelists,
                     "src/middle.h": middle_h, "src/middle.cpp": middle_cpp}, clean_first=True)
        client.run("create . middle/1.0@")
        conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile, CMake

            class Conan(ConanFile):
                name = "consumer"
                version = "1.0"
                generators = "{}", "cmake"
                settings = "os", "compiler", "build_type", "arch"
                exports_sources = "src/*"
                requires = "middle/1.0"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure(source_folder="src")
                    cmake.build()
                    self.run(os.path.join("bin", "main"))
            """.format(generator))
        cmakelists = textwrap.dedent("""
            set(CMAKE_CXX_COMPILER_WORKS 1)
            set(CMAKE_CXX_ABI_COMPILED 1)
            project(consumer CXX)
            cmake_minimum_required(VERSION 3.1)

            include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
            conan_basic_setup()

            find_package(middle)

            get_target_property(tmp middle::middle INTERFACE_LINK_LIBRARIES)
            message("Middle link libraries: ${tmp}")

            add_executable(main main.cpp)
            target_link_libraries(main middle::middle)
            """)
        main_cpp = gen_function_cpp(name="main", includes=["middle"], calls=["middle"])
        client.save({"conanfile.py": conanfile,
                     "src/CMakeLists.txt": cmakelists,
                     "src/main.cpp": main_cpp}, clean_first=True)
        client.run("create . consumer/1.0@")
        # assert False
        assert 'main: Release!' in client.out
        assert 'middle: Release!' in client.out
        assert 'expected/1.0: Hello World Release!' in client.out
        assert 'variant/1.0: Hello World Release!' in client.out
