from conan.tools.cmake.toolchain.toolchain import CMakeToolchain
from conan.tools.cmake.cmake import CMake
from conan.tools.cmake.cmakeconfigdeps.cmakeconfigdeps import CMakeConfigDeps
from conan.tools.cmake.layout import cmake_layout


def CMakeDeps(conanfile):  # noqa
    if conanfile.conf.get("tools.cmake.cmakedeps:new",
                          choices=["will_break_next", "recipe_will_break"]) == "will_break_next":
        conanfile.output.warning("Using the new CMakeConfigDeps generator, behind the "
                                 "'tools.cmake.cmakedeps:new' gate conf. This conf will change "
                                 "next release, breaking, so use it only for testing and dev")
        return CMakeConfigDeps(conanfile)
    from conan.tools.cmake.cmakedeps.cmakedeps import CMakeDeps as _CMakeDeps
    return _CMakeDeps(conanfile)
