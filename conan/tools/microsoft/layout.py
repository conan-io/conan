import os

from conan.tools.microsoft.msbuild import msbuild_arch
from conans.errors import ConanException


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
        bindirs = os.path.join(arch, str(conanfile.settings.build_type))
    else:
        bindirs = str(conanfile.settings.build_type)

    subproject = conanfile.folders.subproject
    conanfile.folders.build = subproject or "."
    conanfile.folders.generators = os.path.join(subproject, "conan") if subproject else "conan"
    conanfile.folders.source = subproject or "."
    conanfile.cpp.build.libdirs = [bindirs]
    conanfile.cpp.build.bindirs = [bindirs]
    conanfile.cpp.source.includedirs = ["include"]
