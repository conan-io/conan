import platform
import shutil
import textwrap

import pytest

from conans.test.assets.sources import gen_function_cpp, gen_function_h
from conans.test.utils.tools import TestClient, TestServer


@pytest.mark.skipif(platform.system() != "Linux", reason="Only Linux")
@pytest.mark.tool_cmake
@pytest.mark.parametrize("soname", [
    "NO_SONAME 1",  # without SONAME
    ""  # By default, with SONAME
])
def test_no_soname_flag(soname):
    """ This test case is testing this graph structure:
            *   'Executable' -> 'LibB' -> 'LibNoSoname'
        Where:
            *   LibNoSoname: is a package built as shared and without the SONAME flag.
            *   LibB: is a package which requires LibNoSoname.
            *   Executable: is the final consumer building an application and depending on OtherLib.
        How:
            1- Creates LibNoSoname and upload it to remote server
            2- Creates LibB and upload it to remote server
            3- Remove the Conan cache folder
            4- Creates an application and consume LibB
    """
    test_server = TestServer()
    servers = {"default": test_server}
    client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
    conanfile = textwrap.dedent("""
    from conans import ConanFile
    from conan.tools.cmake import CMakeToolchain, CMake, cmake_layout

    class {name}Conan(ConanFile):
        name = "{name}"
        version = "1.0"

        # Binary configuration
        settings = "os", "compiler", "build_type", "arch"
        options = {{"shared": [True, False], "fPIC": [True, False]}}
        default_options = {{"shared": True, "fPIC": True}}

        # Sources are located in the same place as this recipe, copy them to the recipe
        exports_sources = "CMakeLists.txt", "src/*"
        {generators}
        {requires}

        def config_options(self):
            if self.settings.os == "Windows":
                del self.options.fPIC

        def layout(self):
            cmake_layout(self)

        def generate(self):
            tc = CMakeToolchain(self)
            tc.generate()

        def build(self):
            cmake = CMake(self)
            cmake.configure()
            cmake.build()

        def package(self):
            cmake = CMake(self)
            cmake.install()

        def package_info(self):
            self.cpp_info.libs = ["{name}"]
    """)
    cmakelists_nosoname = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(nosoname CXX)

        add_library(nosoname SHARED src/nosoname.cpp)

        # Adding NO_SONAME flag to main library
        set_target_properties(nosoname PROPERTIES PUBLIC_HEADER "src/nosoname.h" {})
        install(TARGETS nosoname DESTINATION "."
                PUBLIC_HEADER DESTINATION include
                RUNTIME DESTINATION bin
                ARCHIVE DESTINATION lib
                LIBRARY DESTINATION lib
                )
    """.format(soname))
    cpp = gen_function_cpp(name="nosoname")
    h = gen_function_h(name="nosoname")
    # Creating nosoname library
    client.save({"CMakeLists.txt": cmakelists_nosoname,
                 "src/nosoname.cpp": cpp,
                 "src/nosoname.h": h,
                 "conanfile.py": conanfile.format(name="nosoname", requires="", generators="")})

    client.run("create . lasote/stable")
    # Uploading it to default remote server
    client.run("upload {} --all".format("nosoname/1.0@lasote/stable"))

    cmakelists_libB = textwrap.dedent("""
    cmake_minimum_required(VERSION 3.15)
    project(libB CXX)

    find_package(nosoname CONFIG REQUIRED)

    add_library(libB SHARED src/libB.cpp)
    target_link_libraries(libB nosoname::nosoname)

    set_target_properties(libB PROPERTIES PUBLIC_HEADER "src/libB.h")
    install(TARGETS libB DESTINATION "."
            PUBLIC_HEADER DESTINATION include
            RUNTIME DESTINATION bin
            ARCHIVE DESTINATION lib
            LIBRARY DESTINATION lib
            )
    """)
    cpp = gen_function_cpp(name="libB", includes=["nosoname"], calls=["nosoname"])
    h = gen_function_h(name="libB")
    # Creating libB library that requires nosoname one
    client.save({"CMakeLists.txt": cmakelists_libB,
                 "src/libB.cpp": cpp,
                 "src/libB.h": h,
                 "conanfile.py": conanfile.format(name="libB",
                                                  requires='requires = "nosoname/1.0@lasote/stable"',
                                                  generators='generators = "CMakeDeps"')},
                clean_first=True)

    client.run("create . lasote/stable")
    # Uploading it to default remote server
    client.run("upload {} --all".format("libB/1.0@lasote/stable"))
    # Cleaning the current client cache
    shutil.rmtree(client.cache_folder)

    # Creating the consumer application that requires libB
    client2 = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
    cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(PackageTest CXX)

        find_package(libB CONFIG REQUIRED)

        add_executable(example src/example.cpp)
        target_link_libraries(example libB::libB)
    """)
    conanfile = textwrap.dedent("""
        [requires]
        libB/1.0@lasote/stable

        [generators]
        CMakeDeps
        CMakeToolchain
        VirtualRunEnv
    """)
    cpp = gen_function_cpp(name="main", includes=["libB"], calls=["libB"])
    client2.save({"CMakeLists.txt": cmakelists.format(current_folder=client.current_folder),
                  "src/example.cpp": cpp,
                  "conanfile.txt": conanfile},
                 clean_first=True)
    client2.run('install . ')
    # Activate the VirtualRunEnv and execute the CMakeToolchain
    client2.run_command('bash -c \'source conanrun.sh '
                        ' && cmake -G "Unix Makefiles" -DCMAKE_TOOLCHAIN_FILE="./conan_toolchain.cmake" .'
                        ' && cmake --build . && ./example\'')
