import os

from conans.errors import ConanException


def clion_layout(conanfile):
    if not conanfile.settings.get_safe("build_type"):
        raise ConanException("The 'clion_layout' requires the 'build_type' setting")
    base = "cmake-build-{}".format(str(conanfile.settings.build_type).lower())
    conanfile.layout.build.folder = base
    conanfile.layout.build.cpp_info.libdirs = ["."]

    conanfile.layout.generators.folder = os.path.join(base, "generators")

    conanfile.layout.source.folder = "."
    conanfile.layout.source.cpp_info.includedirs = ["include"]

