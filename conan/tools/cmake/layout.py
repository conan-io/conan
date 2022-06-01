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

    suffix = get_build_folder_vars_suffix(conanfile)
    if multi:
        conanfile.folders.build = "build"
    else:
        conanfile.folders.build = "cmake-build-{}".format(str(build_type).lower())

    if suffix:
        conanfile.folders.build += "-{}".format(suffix)

    conanfile.folders.generators = os.path.join("build" if not suffix else "build-{}".format(suffix),
                                                "generators")

    conanfile.cpp.source.includedirs = ["include"]

    if multi:
        conanfile.cpp.build.libdirs = ["{}".format(build_type)]
        conanfile.cpp.build.bindirs = ["{}".format(build_type)]
    else:
        conanfile.cpp.build.libdirs = ["."]
        conanfile.cpp.build.bindirs = ["."]


def get_build_folder_vars_suffix(conanfile):

    build_vars = conanfile.conf.get("tools.cmake.cmake_layout:build_folder_vars",
                                    default=[], check_type=list)
    ret = []
    for s in build_vars:
        tmp = None
        if s.startswith("settings."):
            _, var = s.split("settings.", 1)
            tmp = conanfile.settings.get_safe(var)
        elif s.startswith("options."):
            _, var = s.split("options.", 1)
            value = conanfile.options.get_safe(var)
            if value is not None:
                tmp = "{}_{}".format(var, value)
        else:
            raise ConanException("Invalid 'tools.cmake.cmake_layout:build_folder_vars' value, it has"
                                 " to start with 'settings.' or 'options.': {}".format(s))
        if tmp:
            ret.append(tmp.lower())

    return "-".join(ret)
