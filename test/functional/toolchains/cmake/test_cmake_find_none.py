import platform
import textwrap

import pytest

from conan.test.utils.tools import TestClient


def test_cmake_find_none_transitive():
    c = TestClient()

    qt = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake

        class pkgRecipe(ConanFile):
            name = "qt"
            version = "0.1"
            package_type = "static-library"

            # Binary configuration
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeToolchain"

            # Sources are located in the same place as this recipe, copy them to the recipe
            exports_sources = "CMakeLists.txt", "src/*", "include/*"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def package(self):
                cmake = CMake(self)
                cmake.install()

            def package_info(self):
                self.cpp_info.builddirs = ["qt/cmake"]
                self.cpp_info.set_property("cmake_find_mode", "none")
                self.cpp_info.set_property("cmake_file_name", "Qt5")
        """)

    cmake = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(MyHello NONE)

        add_library(qt INTERFACE)
        install(TARGETS qt EXPORT Qt5Config)
        export(TARGETS qt
            NAMESPACE qt::
            FILE "${CMAKE_CURRENT_BINARY_DIR}/Qt5Config.cmake"
        )
        install(EXPORT Qt5Config
            DESTINATION "qt/cmake"
            NAMESPACE qt::
        )
        """)
    c.save({"conanfile.py": qt,
            "CMakeLists.txt": cmake})
    c.run("create .")

    karchive = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake

        class pkgRecipe(ConanFile):
            name = "karchive"
            version = "0.1"
            package_type = "static-library"

            requires = "qt/0.1"
        """)

    c.save({"conanfile.py": karchive}, clean_first=True)
    c.run("create .")

    consumer_cmake = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(MyHello NONE)

        find_package(karchive CONFIG REQUIRED)
        """)

    consumer = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake

        class pkgRecipe(ConanFile):
            package_type = "static-library"
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeToolchain", "CMakeDeps"

            def requirements(self):
                self.requires("karchive/0.1")
                self.requires("qt/0.1")

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
        """)

    c.save({"conanfile.py": consumer,
            "CMakeLists.txt": consumer_cmake}, clean_first=True)
    c.run("build .")
    assert "Conan: Target declared 'karchive::karchive'" in c.out
    # And it doesn't fail to find transitive qt


def test_cmake_find_none_relocation():
    c = TestClient(default_server_user=True)
    c.run("new cmake_lib -d name=pkg -d version=0.1")
    conanfile = c.load("conanfile.py")
    conanfile = conanfile + '        self.cpp_info.set_property("cmake_find_mode", "none")'
    conanfile = conanfile + '\n        self.cpp_info.builddirs = ["pkg/cmake"]'

    cmake_export = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(MyHello CXX)

        add_library(pkg src/pkg.cpp)
        target_include_directories(pkg PUBLIC
          $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
          $<INSTALL_INTERFACE:include>
        )
        set_target_properties(pkg PROPERTIES PUBLIC_HEADER "include/pkg.h")

        install(TARGETS pkg EXPORT pkgConfig)
        export(TARGETS pkg
            NAMESPACE pkg::
            FILE "${CMAKE_CURRENT_BINARY_DIR}/pkgConfig.cmake"
        )
        install(EXPORT pkgConfig
            DESTINATION "pkg/cmake"
            NAMESPACE pkg::
        )
        """)

    c.save({"conanfile.py": conanfile,
            "CMakeLists.txt": cmake_export})

    c.run("create . ")
    c.run("upload * -r=default -c")
    c.run("remove * -c")

    c2 = TestClient(servers=c.servers)
    c2.run("new cmake_exe -d name=myapp -d version=0.1 -d requires=pkg/0.1")
    c2.run('build .')
    # Now it builds correctly without failing, because package is relocatable


@pytest.mark.tool("ninja")
# It is IMPORTANT to do cmake-3.27 AFTER ninja, otherwise CI injects another cmake
@pytest.mark.tool("cmake", "3.27")
def test_cmake_find_none_relocation_multi():
    # What happens for multi-config
    c = TestClient(default_server_user=True)
    c.run("new cmake_lib -d name=pkg -d version=0.1")
    conanfile = textwrap.dedent("""
        import os, textwrap
        from conan import ConanFile
        from conan.tools.files import save, load
        from conan.tools.cmake import CMakeToolchain, CMake, cmake_layout, CMakeDeps

        class pkgRecipe(ConanFile):
            name = "pkg"
            version = "0.1"
            package_type = "library"

            settings = "os", "compiler", "build_type", "arch"
            options = {"shared": [True, False], "fPIC": [True, False]}
            default_options = {"shared": False, "fPIC": True}

            # Sources are located in the same place as this recipe, copy them to the recipe
            exports_sources = "CMakeLists.txt", "src/*", "include/*"
            implements = ["auto_shared_fpic"]

            generators = "CMakeToolchain", "CMakeDeps"

            def layout(self):
                cmake_layout(self)

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def package(self):
                cmake = CMake(self)
                cmake.install()
                p = os.path.join(self.package_folder, "pkg", "cmake", "pkgConfig.cmake")
                new_config = textwrap.dedent('''
                    # Create imported target pkg::pkg
                    add_library(pkg::pkg STATIC IMPORTED)

                    if(NOT DEFINED CONAN_pkg_DIR_MULTI)
                        get_filename_component(CONAN_pkg_DIR_MULTI "${CMAKE_CURRENT_LIST_FILE}" PATH)
                    endif()
                    foreach(_IMPORT_PREFIX ${CONAN_pkg_DIR_MULTI})
                        get_filename_component(_IMPORT_PREFIX "${_IMPORT_PREFIX}" PATH)
                        get_filename_component(_IMPORT_PREFIX "${_IMPORT_PREFIX}" PATH)

                        set_target_properties(pkg::pkg PROPERTIES
                          INTERFACE_INCLUDE_DIRECTORIES "${_IMPORT_PREFIX}/include"
                        )

                        # Load information for each installed configuration.
                        file(GLOB CONFIG_FILES "${_IMPORT_PREFIX}/pkg/cmake/pkgConfig-*.cmake")
                        foreach(f ${CONFIG_FILES})
                          include(${f})
                        endforeach()
                    endforeach()
                    ''')
                save(self, p, new_config)

            def package_info(self):
                self.cpp_info.libs = ["pkg"]
                self.cpp_info.set_property("cmake_find_mode", "none")
                self.cpp_info.builddirs = ["pkg/cmake"]
        """)

    cmake_export = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(MyHello CXX)

        add_library(pkg src/pkg.cpp)
        target_include_directories(pkg PUBLIC
          $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
          $<INSTALL_INTERFACE:include>
        )
        set_target_properties(pkg PROPERTIES PUBLIC_HEADER "include/pkg.h")

        install(TARGETS pkg EXPORT pkgConfig)
        export(TARGETS pkg
            NAMESPACE pkg::
            FILE "${CMAKE_CURRENT_BINARY_DIR}/pkgConfig.cmake"
        )
        install(EXPORT pkgConfig
            DESTINATION "pkg/cmake"
            NAMESPACE pkg::
        )
        """)

    c.save({"conanfile.py": conanfile,
            "CMakeLists.txt": cmake_export})

    c.run("create .")
    c.run("create . -s build_type=Debug")
    c.run("upload * -r=default -c")
    c.run("remove * -c")

    c2 = TestClient(servers=c.servers)
    c2.run("new cmake_exe -d name=myapp -d version=0.1 -d requires=pkg/0.1")
    env = r".\build\generators\conanbuild.bat &&" if platform.system() == "Windows" else ""
    conf = ('-c tools.cmake.cmaketoolchain:generator="Ninja Multi-Config" '
            '-c tools.cmake.cmakedeps:new=will_break_next')
    c2.run(f'install . {conf}')
    c2.run(f'install . {conf} -s build_type=Debug')
    c2.run_command(f"{env} cmake --preset conan-default")
    c2.run_command(f"{env} cmake --build --preset conan-release")
    c2.run_command(f"{env} cmake --build --preset conan-debug")
