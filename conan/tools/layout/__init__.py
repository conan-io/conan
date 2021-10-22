import os

from conan.tools.microsoft.msbuild import msbuild_arch
from conans.errors import ConanException


def cmake_layout(conanfile, generator=None):
    gen = conanfile.conf["tools.cmake.cmaketoolchain:generator"] or generator
    if gen:
        multi = "Visual" in gen or "Xcode" in gen or "Multi-Config" in gen
    elif conanfile.settings.compiler == "Visual Studio" or conanfile.settings.compiler == "msvc":
        multi = True
    else:
        multi = False

    conanfile.folders.source = "."
    if multi:
        conanfile.folders.build = "build"
        conanfile.folders.generators = "build/conan"
    else:
        build_type = str(conanfile.settings.build_type).lower()
        conanfile.folders.build = "cmake-build-{}".format(build_type)
        conanfile.folders.generators = os.path.join(conanfile.folders.build, "conan")

    conanfile.cpp.local.includedirs = ["src"]
    if multi:
        libdir = os.path.join(conanfile.folders.build, str(conanfile.settings.build_type))
        conanfile.cpp.local.libdirs = [libdir]
    else:
        conanfile.cpp.local.libdirs = [conanfile.folders.build]
        conanfile.cpp.local.bindirs = [conanfile.folders.build]


def clion_layout(conanfile):
    if not conanfile.settings.get_safe("build_type"):
        raise ConanException("The 'clion_layout' requires the 'build_type' setting")
    base = "cmake-build-{}".format(str(conanfile.settings.build_type).lower())
    conanfile.folders.build = base
    conanfile.cpp.local.libdirs = [conanfile.folders.build]
    conanfile.folders.generators = os.path.join(base, "generators")
    conanfile.folders.source = "."
    conanfile.cpp.local.includedirs = [conanfile.folders.source]


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
    conanfile.cpp.local.libdirs = [conanfile.folders.build]
    conanfile.folders.generators = os.path.join(base, "generators")
    conanfile.folders.source = "."
    conanfile.cpp.local.includedirs = [conanfile.folders.source]
