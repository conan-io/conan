from conan.tools.cmake.toolchain.toolchain import CMakeToolchain
from conan.tools.cmake.cmake import CMake
from conan.tools.cmake.layout import cmake_layout


def CMakeDeps(conanfile):  # noqa
    if conanfile.conf.get("tools.cmake.cmakedeps:new", choices=["will_break_next"]):
        from conan.tools.cmake.cmakedeps2.cmakedeps import CMakeDeps2
        return CMakeDeps2(conanfile)
    from conan.tools.cmake.cmakedeps.cmakedeps import CMakeDeps as _CMakeDeps
    return _CMakeDeps(conanfile)
