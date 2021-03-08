import os

from conans.errors import ConanException


# FIXME: Not documented, just a POC, missing a way to do something similar without modifying
#        the recipe

def clion_layout(conanfile):
    if not conanfile.settings.get_safe("build_type"):
        raise ConanException("The 'clion_layout' requires the 'build_type' setting")
    base = "cmake-build-{}".format(str(conanfile.settings.build_type).lower())
    conanfile.folders.build.folder = base
    conanfile.folders.build.cpp_info.libdirs = ["."]

    conanfile.folders.generators.folder = os.path.join(base, "generators")

    conanfile.folders.source.folder = "."
    conanfile.folders.source.cpp_info.includedirs = ["include"]
