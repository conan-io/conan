import textwrap

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
            DESTINATION "${CMAKE_INSTALL_PREFIX}/qt/cmake"
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
