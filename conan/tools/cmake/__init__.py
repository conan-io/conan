from conan.tools.cmake.toolchain.toolchain import CMakeToolchain
from conan.tools.cmake.cmake import CMake
from conan.tools.cmake.cmakeconfigdeps.cmakeconfigdeps import CMakeConfigDeps
from conan.tools.cmake.layout import cmake_layout


def CMakeDeps(conanfile):  # noqa
    if conanfile.conf.get("tools.cmake.cmakedeps:new",
                          choices=["will_break_next", "recipe_will_break"]) == "will_break_next":
        conanfile.output.warning("On the fly replacement of CMakeDeps by CMakeConfigDeps generator, "
                                 "because 'tools.cmake.cmakedeps:new' incubating conf activated. "
                                 "This conf is incubating and will break in next releases. "
                                 "CMakeConfigDeps is now experimental and can be used as such in "
                                 "recipes.")
        return CMakeConfigDeps(conanfile)
    from conan.tools.cmake.cmakedeps.cmakedeps import CMakeDeps as _CMakeDeps
    return _CMakeDeps(conanfile)
