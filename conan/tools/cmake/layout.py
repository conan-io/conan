import os

from conans.errors import ConanException


def cmake_layout(conanfile, generator=None):
    gen = conanfile.conf.get("tools.cmake.cmaketoolchain:generator", default=generator)
    if gen:
        multi = "Visual" in gen or "Xcode" in gen or "Multi-Config" in gen
    else:
        compiler = conanfile.settings.get_safe("compiler")
        if compiler in ("Visual Studio", "msvc"):
            multi = True
        else:
            multi = False

    conanfile.folders.source = "."
    try:
        build_type = str(conanfile.settings.build_type)
    except ConanException:
        raise ConanException("'build_type' setting not defined, it is necessary for cmake_layout()")
    default_build = "build" if multi else "cmake-build-{build_type_lower}"
    build_folder = conanfile.conf.get("tools.cmake.layout:build_folder", default=default_build)
    build_folder = build_folder.format(build_type=build_type,
                                       build_type_lower=build_type.lower())
    conanfile.folders.build = build_folder
    conanfile.folders.generators = "{}/conan".format(build_folder)

    conanfile.cpp.source.includedirs = ["src"]
    if multi:
        conanfile.cpp.build.libdirs = ["{}".format(build_type)]
        conanfile.cpp.build.bindirs = ["{}".format(build_type)]
    else:
        conanfile.cpp.build.libdirs = ["."]
        conanfile.cpp.build.bindirs = ["."]


def clion_layout(conanfile):
    if not conanfile.settings.get_safe("build_type"):
        raise ConanException("The 'clion_layout' requires the 'build_type' setting")
    base = "cmake-build-{}".format(str(conanfile.settings.build_type).lower())
    conanfile.folders.build = base
    conanfile.cpp.build.libdirs = ["."]
    conanfile.folders.generators = os.path.join(base, "generators")
    conanfile.folders.source = "."
    conanfile.cpp.source.includedirs = ["."]
