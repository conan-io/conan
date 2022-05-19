import os

from conans.errors import ConanException


def cmake_layout(conanfile, generator=None, src_folder="."):
    gen = conanfile.conf.get("tools.cmake.cmaketoolchain:generator", default=generator)
    if gen:
        multi = "Visual" in gen or "Xcode" in gen or "Multi-Config" in gen
    else:
        compiler = conanfile.settings.get_safe("compiler")
        if compiler in ("Visual Studio", "msvc"):
            multi = True
        else:
            multi = False

    conanfile.folders.source = src_folder
    try:
        build_type = str(conanfile.settings.build_type)
    except ConanException:
        raise ConanException("'build_type' setting not defined, it is necessary for cmake_layout()")

    suffix = get_custom_settings_suffix(conanfile)
    if multi:
        conanfile.folders.build = "build"
    else:
        conanfile.folders.build = "cmake-build-{}".format(str(build_type).lower())

    if suffix:
        conanfile.folders.build += "-{}".format(suffix)

    conanfile.folders.generators = os.path.join("build", "generators")
    if suffix:
        conanfile.folders.generators += "-{}".format(suffix)

    conanfile.cpp.source.includedirs = ["include"]

    if multi:
        conanfile.cpp.build.libdirs = ["{}".format(build_type)]
        conanfile.cpp.build.bindirs = ["{}".format(build_type)]
    else:
        conanfile.cpp.build.libdirs = ["."]
        conanfile.cpp.build.bindirs = ["."]


def get_custom_settings_suffix(conanfile):

    build_settings = conanfile.conf.get("tools.cmake.cmake_layout.custom_settings",
                                        default=[], check_type=list)
    ret = []
    for s in build_settings:
        tmp = conanfile.settings.get_safe(s)
        if tmp:
            ret.append(tmp.lower())

    if not ret:
        return ""

    return "-".join(ret)
