import os


def clion_layout(conanfile):
    base = "cmake-build-{}".format(str(conanfile.settings.build_type).lower())
    conanfile.layout.build.folder = base
    conanfile.layout.build.cpp_info.libdirs = ["."]

    conanfile.layout.generators.folder = os.path.join(base, "generators")

    conanfile.layout.source.folder = "."
    conanfile.layout.source.cpp_info.includedirs = ["include"]

