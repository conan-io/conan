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
        from conans import ConanFile
        from conan.tools.cmake import CMake

        class GreetingsConan(ConanFile):
            name = "greetings"
            version = "0.0.1"
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeDeps", "CMakeToolchain"
            exports_sources = "src/*"
            options = {"components": ["standard", "custom", "none"]}
            default_options = {"components": "standard"}

            def build(self):
                cmake = CMake(self)
                cmake.configure(build_script_folder="src")
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
                    self.cpp_info.set_property("cmake_file_name", "MYG")
                    self.cpp_info.set_property("cmake_target_name", "MyGreetings::MyGreetings")

                    self.cpp_info.components["hello"].set_property("cmake_target_name", "MyGreetings::MyHello")
                    self.cpp_info.components["bye"].set_property("cmake_target_name", "MyGreetings::MyBye")

                    self.cpp_info.components["hello"].libs = ["hello"]
                    self.cpp_info.components["bye"].libs = ["bye"]
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

        add_library(hello hello.cpp)
        add_library(bye bye.cpp)
        """)

    test_package_greetings_conanfile = textwrap.dedent("""
        import os
        from conans import ConanFile
        from conan.tools.cmake import CMake

        class GreetingsTestConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeDeps", "CMakeToolchain"
            requires = "greetings/0.0.1"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def test(self):
                path = "{}".format(self.settings.build_type) if self.settings.os == "Windows" else "."
                self.run("{}{}example".format(path, os.sep))
        """)
    test_package_greetings_cpp = gen_function_cpp(name="main", includes=["hello", "bye"],
                                                  calls=["hello", "bye"])

    test_package_greetings_cmakelists = textwrap.dedent("""
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
        cmake_minimum_required(VERSION 3.0)
        project(PackageTest CXX)

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


def create_chat(client, components, package_info, cmake_find, test_cmake_find):
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.cmake import CMake

        class Chat(ConanFile):
            name = "chat"
            version = "0.0.1"
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeDeps", "CMakeToolchain"
            exports_sources = "src/*"
            requires = "greetings/0.0.1"
            default_options = {{"greetings:components": "{}"}}

            def build(self):
                cmake = CMake(self)
                cmake.configure(build_script_folder="src")
                cmake.build()

            def package(self):
                self.copy("*.h", dst="include", src="src")
                self.copy("*.lib", dst="lib", keep_path=False)
                self.copy("*.a", dst="lib", keep_path=False)

            def package_info(self):
                {}
        """).format(components, "\n        ".join(package_info.splitlines()))
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

        %s
        """ % cmake_find)

    test_conanfile = textwrap.dedent("""
        import os
        from conans import ConanFile
        from conan.tools.cmake import CMake

        class WorldTestConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeDeps", "CMakeToolchain"
            requires = "chat/0.0.1"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def test(self):
                path = "{}".format(self.settings.build_type) if self.settings.os == "Windows" else "."
                self.run("{}{}example".format(path, os.sep))
                self.run("{}{}example2".format(path, os.sep))
        """)
    test_example_cpp = gen_function_cpp(name="main", includes=["sayhellobye"], calls=["sayhellobye"])

    test_cmakelists = textwrap.dedent("""
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
        cmake_minimum_required(VERSION 3.15)
        project(PackageTest CXX)

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


def test_standard_names(setup_client_with_greetings):
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

    create_chat(client, "standard", package_info, cmake_find, test_cmake_find)

    # Test consumer multi-config
    if platform.system() == "Windows":
        with client.chdir("test_package"):
            client.run("install . -s build_type=Release")
            client.run("install . -s build_type=Debug")
            client.run_command('cmake . -DCMAKE_TOOLCHAIN_FILE=conan_toolchain.cmake')
            client.run_command("cmake --build . --config Debug")
            client.run_command(r".\Debug\example.exe")
            assert "sayhellobye: Debug!" in client.out
            assert "sayhello: Debug!" in client.out
            assert "hello: Debug!" in client.out
            assert "bye: Debug!" in client.out
            client.run_command("cmake --build . --config Release")
            client.run_command(r".\Release\example.exe")
            assert "sayhellobye: Release!" in client.out
            assert "sayhello: Release!" in client.out
            assert "hello: Release!" in client.out
            assert "bye: Release!" in client.out


def test_custom_names(setup_client_with_greetings):
    client = setup_client_with_greetings

    package_info = textwrap.dedent("""
        # NOTE: For the new CMakeDeps only filenames mean filename, it is not using the "names" field
        self.cpp_info.set_property("cmake_target_name", "MyChat::MyChat")
        self.cpp_info.set_property("cmake_file_name", "MyChat")

        self.cpp_info.components["sayhello"].set_property("cmake_target_name", "MyChat::MySay")

        self.cpp_info.components["sayhello"].requires = ["greetings::hello"]
        self.cpp_info.components["sayhello"].libs = ["sayhello"]
        self.cpp_info.components["sayhellobye"].set_property("cmake_target_name", "MyChat::MySayBye")

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
    create_chat(client, "custom", package_info, cmake_find, test_cmake_find)


def test_different_namespace(setup_client_with_greetings):
    client = setup_client_with_greetings

    package_info = textwrap.dedent("""
        self.cpp_info.set_property("cmake_target_name", "MyChat::MyGlobalChat")
        self.cpp_info.set_property("cmake_file_name", "MyChat")

        self.cpp_info.components["sayhello"].set_property("cmake_target_name", "MyChat::MySay")

        self.cpp_info.components["sayhello"].requires = ["greetings::hello"]
        self.cpp_info.components["sayhello"].libs = ["sayhello"]
        self.cpp_info.components["sayhellobye"].set_property("cmake_target_name", "MyChat::MySayBye")

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
        target_link_libraries(example2 MyChat::MyGlobalChat)
        """)
    create_chat(client, "custom", package_info, cmake_find, test_cmake_find)



def test_no_components(setup_client_with_greetings):
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
    create_chat(client, "none", package_info, cmake_find, test_cmake_find)


@pytest.mark.slow
@pytest.mark.tool_cmake
def test_same_names():
    client = TestClient()
    conanfile_greetings = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.cmake import CMake

        class HelloConan(ConanFile):
            name = "hello"
            version = "0.0.1"
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeDeps", "CMakeToolchain"
            exports_sources = "src/*"

            def build(self):
                cmake = CMake(self)
                cmake.configure(build_script_folder="src")
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

        add_library(hello hello.cpp)
        """)
    test_package_greetings_conanfile = textwrap.dedent("""
        import os
        from conans import ConanFile
        from conan.tools.cmake import CMake

        class HelloTestConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeDeps", "CMakeToolchain"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def test(self):
                path = "{}".format(self.settings.build_type) if self.settings.os == "Windows" else "."
                self.run("{}{}example".format(path, os.sep))
        """)
    test_package_greetings_cpp = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])

    test_package_greetings_cmakelists = textwrap.dedent("""
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
        cmake_minimum_required(VERSION 3.0)
        project(PackageTest CXX)

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
        """)
        client.save({"conanfile.py": conanfile})
        client.run("create . world/0.0.1@")
        client.run("install world/0.0.1@ -g CMakeDeps", assert_error=True)
        assert ("Component 'greetings::non-existent' not found in 'greetings' "
                "package requirement" in client.out)

    def test_component_not_found_same_name_as_pkg_require(self):
        zlib = GenConanfile("zlib", "0.1").with_setting("build_type").with_generator("CMakeDeps")
        mypkg = GenConanfile("mypkg", "0.1").with_setting("build_type").with_generator("CMakeDeps")
        final = GenConanfile("final", "0.1").with_setting("build_type").with_generator("CMakeDeps")\
            .with_require(ConanFileReference("zlib", "0.1", None, None))\
            .with_require(ConanFileReference("mypkg", "0.1", None, None))\
            .with_package_info(cpp_info={"components": {"cmp": {"requires": ["mypkg::zlib",
                                                                             "zlib::zlib"]}}},
                               env_info={})
        consumer = GenConanfile("consumer", "0.1").with_setting("build_type")\
            .with_generator("CMakeDeps")\
            .with_requirement(ConanFileReference("final", "0.1", None, None))

        consumer = textwrap.dedent("""
            from conans import ConanFile
            from conan.tools.cmake import CMakeDeps
            class HelloConan(ConanFile):
                name = 'consumer'
                version = '0.1'

                def generate(self):
                    deps = CMakeDeps(self)
                    deps.check_components_exist = True
                    deps.generate()

                def requirements(self):
                    self.requires("final/0.1")

                settings = "build_type"
            """)

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
            """)
            client.save({"conanfile.py": conanfile})
            client.run("create . world/0.0.1@")
            client.run("install world/0.0.1@ -g CMakeDeps", assert_error=True)
            assert ("Component 'greetings::non-existent' not found in 'greetings' "
                    "package requirement" in client.out)

        client = TestClient()
        client.save({"zlib.py": zlib, "mypkg.py": mypkg, "final.py": final, "consumer.py": consumer})
        client.run("create zlib.py")
        client.run("create mypkg.py")
        client.run("create final.py")
        client.run("install consumer.py", assert_error=True)
        assert "Component 'mypkg::zlib' not found in 'mypkg' package requirement" in client.out

    @pytest.mark.slow
    def test_same_name_global_target_collision(self):
        # https://github.com/conan-io/conan/issues/7889
        conanfile_tpl = textwrap.dedent("""
            from conans import ConanFile
            from conan.tools.cmake import CMake

            class Conan(ConanFile):
                name = "{name}"
                version = "1.0"
                settings = "os", "compiler", "build_type", "arch"
                generators = "CMakeDeps", "CMakeToolchain"
                exports_sources = "src/*"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure(build_script_folder="src")
                    cmake.build()

                def package(self):
                    self.copy("*.h", dst="include", src="src")
                    self.copy("*.lib", dst="lib", keep_path=False)
                    self.copy("*.a", dst="lib", keep_path=False)

                def package_info(self):
                    self.cpp_info.set_property("cmake_target_name", "nonstd::nonstd" )
                    self.cpp_info.set_property("cmake_file_name", "{name}")

                    self.cpp_info.components["1"].set_property("cmake_target_name", "nonstd::{name}")
                    self.cpp_info.components["1"].libs = ["{name}"]
            """)
        basic_cmake = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.15)
            set(CMAKE_CXX_COMPILER_WORKS 1)
            set(CMAKE_CXX_ABI_COMPILED 1)
            project(middle CXX)
            add_library({name} {name}.cpp)
            """)
        client = TestClient()
        for name in ["expected", "variant"]:
            client.run("new {name}/1.0 -s".format(name=name))
            client.save({"conanfile.py": conanfile_tpl.format(name=name),
                         "src/CMakeLists.txt": basic_cmake.format(name=name)})
            client.run("create . {name}/1.0@".format(name=name))
        middle_cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.15)
            set(CMAKE_CXX_COMPILER_WORKS 1)
            set(CMAKE_CXX_ABI_COMPILED 1)
            project(middle CXX)

            find_package(expected)
            find_package(variant)

            add_library(middle middle.cpp)
            target_link_libraries(middle nonstd::nonstd)
            """)
        middle_h = gen_function_h(name="middle")
        middle_cpp = gen_function_cpp(name="middle", includes=["middle", "expected", "variant"],
                                      calls=["expected", "variant"])
        middle_conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conan.tools.cmake import CMake

            class Conan(ConanFile):
                name = "middle"
                version = "1.0"
                settings = "os", "compiler", "build_type", "arch"
                generators = "CMakeDeps", "CMakeToolchain"
                exports_sources = "src/*"
                requires = "expected/1.0", "variant/1.0"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure(build_script_folder="src")
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
            from conans import ConanFile
            from conan.tools.cmake import CMake, cmake_layout

            class Conan(ConanFile):
                name = "consumer"
                version = "1.0"
                generators = "CMakeDeps", "CMakeToolchain"
                settings = "os", "compiler", "build_type", "arch"
                exports_sources = "src/*"
                requires = "middle/1.0"

                def layout(self):
                    cmake_layout(self)

                def build(self):
                    cmake = CMake(self)
                    cmake.configure(build_script_folder="src")
                    cmake.build()
                    cmd = os.path.join(self.cpp.build.bindirs[0], "main")
                    self.run(cmd, env="conanrun")
            """)
        cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.15)
            set(CMAKE_CXX_COMPILER_WORKS 1)
            set(CMAKE_CXX_ABI_COMPILED 1)
            project(consumer CXX)

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

        assert 'main: Release!' in client.out
        assert 'middle: Release!' in client.out
        assert 'expected/1.0: Hello World Release!' in client.out
        assert 'variant/1.0: Hello World Release!' in client.out


@pytest.mark.parametrize("check_components_exist", [False, True, None])
def test_targets_declared_in_build_modules(check_components_exist):
    """If a require is declaring the component targets in a build_module, CMakeDeps is
       fine with it, not needed to locate it as a conan declared component"""

    client = TestClient()
    conanfile_hello = str(GenConanfile().with_name("hello").with_version("1.0")
                          .with_exports_sources("*.cmake", "*.h"))
    conanfile_hello += """
    def package(self):
        self.copy("*.h", dst="include")
        self.copy("*.cmake", dst="cmake")

    def package_info(self):
        self.cpp_info.set_property("cmake_build_modules", ["cmake/my_modules.cmake"])
    """
    my_modules = textwrap.dedent("""
    add_library(cool_component INTERFACE)
    target_include_directories(cool_component INTERFACE ${CMAKE_CURRENT_LIST_DIR}/../include/)
    add_library(hello::invented ALIAS cool_component)
    """)
    hello_h = "int cool_header_only=1;"
    client.save({"conanfile.py": conanfile_hello,
                 "my_modules.cmake": my_modules, "hello.h": hello_h})
    client.run("create .")

    conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conan.tools.cmake import CMake, CMakeDeps

            class HelloConan(ConanFile):
                name = 'app'
                version = '1.0'
                exports_sources = "*.txt", "*.cpp"
                generators = "CMakeToolchain"
                requires = ("hello/1.0", )
                settings = "os", "compiler", "arch", "build_type"

                def generate(self):
                    deps = CMakeDeps(self)
                    {}
                    deps.generate()

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                    cmake.build()

    """)
    if check_components_exist is False:
        conanfile = conanfile.format("deps.check_components_exist=False")
    elif check_components_exist is True:
        conanfile = conanfile.format("deps.check_components_exist=True")
    else:
        conanfile = conanfile.format("")

    main_cpp = textwrap.dedent("""
        #include <iostream>
        #include "hello.h"

        int main(){
            std::cout << "cool header value: " << cool_header_only;
            return 0;
        }
        """)

    cmakelist = textwrap.dedent("""
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
        set(CMAKE_C_COMPILER_WORKS 1)
        set(CMAKE_C_ABI_COMPILED 1)
        cmake_minimum_required(VERSION 3.15)
        project(project CXX)

        find_package(hello COMPONENTS hello::invented missing)
        add_executable(myapp main.cpp)
        target_link_libraries(myapp hello::invented)
    """)
    client.save({"conanfile.py": conanfile,
                 "CMakeLists.txt": cmakelist, "main.cpp": main_cpp})
    client.run("create .", assert_error=check_components_exist)
    assert bool(check_components_exist) == ("Conan: Component 'missing' NOT found in package "
                                            "'hello'" in client.out)

    assert "Conan: Including build module" in client.out
    assert "my_modules.cmake" in client.out
    assert bool(check_components_exist) == ("Conan: Component 'hello::invented' found in package 'hello'"
                                            in client.out)


@pytest.mark.tool_cmake
def test_cmakedeps_targets_no_namespace():
    """
    This test is checking that when we add targets with no namespace for the root cpp_info
    and the components, the targets are correctly generated. Before Conan 1.43, Conan
    only generated targets with namespace
    """
    client = TestClient()
    my_pkg = textwrap.dedent("""
        from conans import ConanFile
        class MyPkg(ConanFile):
            name = "my_pkg"
            version = "0.1"
            settings = "os", "arch", "compiler", "build_type"
            def package_info(self):
                self.cpp_info.set_property("cmake_target_name", "nonamespacepkg")
                self.cpp_info.components["MYPKGCOMP"].set_property("cmake_target_name", "MYPKGCOMPNAME")
        """)
    client.save({"my_pkg/conanfile.py": my_pkg}, clean_first=True)
    client.run("create my_pkg")

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class LibcurlConan(ConanFile):
            name = "libcurl"
            version = "0.1"
            requires = "my_pkg/0.1"
            settings = "os", "arch", "compiler", "build_type"
            def package_info(self):
                self.cpp_info.set_property("cmake_target_name", "CURL")
                self.cpp_info.set_property("cmake_file_name", "CURLFILENAME")
                self.cpp_info.components["curl"].set_property("cmake_target_name", "libcurl")
                self.cpp_info.components["curl2"].set_property("cmake_target_name", "libcurl2")
                self.cpp_info.components["curl2"].requires.extend(["curl", "my_pkg::MYPKGCOMP"])
        """)
    client.save({"libcurl/conanfile.py": conanfile})
    client.run("create libcurl")

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.cmake import CMakeDeps, CMake, CMakeToolchain
        class Consumer(ConanFile):
            name = "consumer"
            version = "0.1"
            requires = "libcurl/0.1"
            settings = "os", "arch", "compiler", "build_type"
            exports_sources = "CMakeLists.txt"
            def generate(self):
                deps = CMakeDeps(self)
                deps.check_components_exist=True
                deps.generate()
                tc = CMakeToolchain(self)
                tc.generate()
            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
        """)

    cmakelists = textwrap.dedent("""cmake_minimum_required(VERSION 3.15)
        project(Consumer)
        find_package(CURLFILENAME CONFIG REQUIRED COMPONENTS libcurl libcurl2)
        """)

    client.save({"consumer/conanfile.py": conanfile, "consumer/CMakeLists.txt": cmakelists})
    client.run("create consumer")
    assert "Component target declared 'libcurl'" in client.out
    assert "Component target declared 'libcurl2'" in client.out
    assert "Target declared 'CURL'" in client.out
    assert "Component target declared 'MYPKGCOMPNAME'" in client.out
    assert "Target declared 'nonamespacepkg'" in client.out
