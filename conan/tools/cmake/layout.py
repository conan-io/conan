import os

from conans.errors import ConanException


def cmake_layout(conanfile, generator=None, src_folder="."):
    gen = conanfile.conf.get("tools.cmake.cmaketoolchain:generator", default=generator)
    if gen:
        multi = "Visual" in gen or "Xcode" in gen or "Multi-Config" in gen
    else:
        compiler = conanfile.settings.get_safe("compiler")
        if compiler == "msvc":
            multi = True
        else:
            multi = False

    conanfile.folders.source = src_folder
    try:
        build_type = str(conanfile.settings.build_type)
    except ConanException:
        raise ConanException("'build_type' setting not defined, it is necessary for cmake_layout()")
    if multi:
        conanfile.folders.build = "build"
        conanfile.folders.generators = "build/conan"
    else:
        build_type = build_type.lower()
        conanfile.folders.build = "cmake-build-{}".format(build_type)
        conanfile.folders.generators = os.path.join(conanfile.folders.build, "conan")

    conanfile.cpp.source.includedirs = ["include"]

    if multi:
        conanfile.cpp.build.libdirs = ["{}".format(build_type)]
        conanfile.cpp.build.bindirs = ["{}".format(build_type)]
    else:
        conanfile.cpp.build.libdirs = ["."]
        conanfile.cpp.build.bindirs = ["."]
