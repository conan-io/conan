import textwrap

from conan.test.assets.sources import gen_function_cpp


def test_aggregator(transitive_libraries):
    c = transitive_libraries

    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.cmake import CMake, cmake_layout
        class Pkg(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            requires = "engine/1.0"
            generators = "CMakeDeps", "CMakeToolchain"
            exports_sources = "*"
            def layout(self):
                cmake_layout(self)
            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
                self.run(os.path.join(self.cpp.build.bindir, "app"))
        """)

    cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
        project(app CXX)
        include(${CMAKE_BINARY_DIR}/generators/conandeps_legacy.cmake)
        add_executable(app main.cpp)
        target_link_libraries(app ${CONANDEPS_LEGACY})
        """)

    c.save({
        "conanfile.py": conanfile,
        "main.cpp": gen_function_cpp(name="main", includes=["engine"], calls=["engine"]),
        "CMakeLists.txt": cmakelists
    }, clean_first=True)
    c.run("build .")
    assert "matrix/1.0: Hello World Release!" in c.out
    assert "engine/1.0: Hello World Release!" in c.out
