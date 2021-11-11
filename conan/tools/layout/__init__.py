import os

from conan.tools.microsoft.msbuild import msbuild_arch
from conans.errors import ConanException


def cmake_layout(conanfile, generator=None):
    gen = conanfile.conf["tools.cmake.cmaketoolchain:generator"] or generator
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
    if multi:
        conanfile.folders.build = "build"
        conanfile.folders.generators = "build/conan"
    else:
        build_type = build_type.lower()
        conanfile.folders.build = "cmake-build-{}".format(build_type)
        conanfile.folders.generators = os.path.join(conanfile.folders.build, "conan")

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


def vs_layout(conanfile):
    if not conanfile.settings.get_safe("build_type"):
        raise ConanException("The 'vs_layout' requires the 'build_type' setting")
    if not conanfile.settings.get_safe("arch"):
        raise ConanException("The 'vs_layout' requires the 'arch' setting")

    if conanfile.settings.arch != "x86":
        arch = msbuild_arch(conanfile.settings.arch)
        if not arch:
            raise ConanException("The 'vs_layout' doesn't "
                                 "work with the arch '{}'".format(conanfile.settings.arch))
        base = "{}/{}".format(arch, str(conanfile.settings.build_type))
    else:
        base = str(conanfile.settings.build_type)

    conanfile.folders.build = base
    conanfile.cpp.build.libdirs = ["."]
    conanfile.folders.generators = os.path.join(base, "generators")
    conanfile.folders.source = "."
    conanfile.cpp.source.includedirs = ["."]
