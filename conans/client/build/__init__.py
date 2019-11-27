from conans.errors import ConanException
from conans.model.conan_file import ConanFile


def defs_to_string(defs):
    return " ".join(['-D{0}="{1}"'.format(k, v) for k, v in defs.items()])


def join_arguments(args):
    return " ".join(filter(None, args))


def CMake(conanfile, *args, **kwargs):
    if not isinstance(conanfile, ConanFile):
        raise ConanException("First argument of CMake() has to be ConanFile. Use CMake(self)")

    from conans.client.build.cmake import CMakeBuildHelper
    from conans.client.build.cmake_toolchain_build_helper import CMakeToolchainBuildHelper

    # If there is a toolchain, then use the toolchain helper one
    toolchain_method = getattr(conanfile, "toolchain", None)
    if toolchain_method:
        if not callable(toolchain_method):
            raise ConanException("Member 'toolchain' in your ConanFile has to be a function"
                                 " returning a CMakeToolchain object")
        return CMakeToolchainBuildHelper(conanfile, *args, **kwargs)
    else:
        return CMakeBuildHelper(conanfile, *args, **kwargs)
