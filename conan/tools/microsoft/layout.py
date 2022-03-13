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
        base = os.path.join(arch, str(conanfile.settings.build_type))
    else:
        base = str(conanfile.settings.build_type)

    conanfile.folders.build = "."
    conanfile.folders.generators = "conan"
    conanfile.folders.source = "."
    conanfile.cpp.build.libdirs = [base]
    conanfile.cpp.build.bindirs = [base]
    conanfile.cpp.source.includedirs = ["include"]
