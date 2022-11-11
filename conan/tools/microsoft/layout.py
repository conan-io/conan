import os

from conan.tools.microsoft.msbuild import msbuild_arch
from conans.errors import ConanException


def vs_layout(conanfile):
    """
    Initialize a layout for a typical Visual Studio project.

    :param conanfile: ``< ConanFile object >`` The current recipe object. Always use ``self``.
    """
    conanfile.folders.test_output = ""
    subproject = conanfile.folders.subproject
    conanfile.folders.source = subproject or "."
    conanfile.folders.generators = os.path.join(subproject, "conan") if subproject else "conan"
    conanfile.folders.build = subproject or "."
    conanfile.cpp.source.includedirs = ["include"]

    try:
        build_type = str(conanfile.settings.build_type)
    except ConanException:
        raise ConanException("The 'vs_layout' requires the 'build_type' setting")
    try:
        arch = str(conanfile.settings.arch)
    except ConanException:
        raise ConanException("The 'vs_layout' requires the 'arch' setting")

    if arch != "None" and arch != "x86":
        arch = msbuild_arch(arch)
        if not arch:
            raise ConanException("The 'vs_layout' doesn't "
                                 "work with the arch '{}'".format(arch))
        bindirs = os.path.join(arch, build_type)
    else:
        bindirs = build_type

    conanfile.cpp.build.libdirs = [bindirs]
    conanfile.cpp.build.bindirs = [bindirs]
