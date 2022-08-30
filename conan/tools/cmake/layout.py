import os

from conans.errors import ConanException


def cmake_layout(conanfile, generator=None, src_folder=".", build_folder="build"):
    gen = conanfile.conf.get("tools.cmake.cmaketoolchain:generator", default=generator)
    if gen:
        multi = "Visual" in gen or "Xcode" in gen or "Multi-Config" in gen
    else:
        compiler = conanfile.settings.get_safe("compiler")
        if compiler in ("Visual Studio", "msvc"):
            multi = True
        else:
            multi = False

    subproject = conanfile.folders.subproject
    conanfile.folders.source = src_folder if not subproject else os.path.join(subproject, src_folder)
    try:
        build_type = str(conanfile.settings.build_type)
    except ConanException:
        raise ConanException("'build_type' setting not defined, it is necessary for cmake_layout()")

    build_folder = build_folder if not subproject else os.path.join(subproject, build_folder)
    custom_conf = get_build_folder_custom_vars(conanfile)
    if custom_conf:
        build_folder = os.path.join(build_folder, custom_conf)

    if multi:
        conanfile.folders.build = build_folder
    else:
        conanfile.folders.build = os.path.join(build_folder, build_type)

    conanfile.folders.generators = os.path.join(build_folder, "generators")

    conanfile.cpp.source.includedirs = ["include"]

    if multi:
        conanfile.cpp.build.libdirs = ["{}".format(build_type)]
        conanfile.cpp.build.bindirs = ["{}".format(build_type)]
    else:
        conanfile.cpp.build.libdirs = ["."]
        conanfile.cpp.build.bindirs = ["."]


def get_build_folder_custom_vars(conanfile):

    build_vars = conanfile.conf.get("tools.cmake.cmake_layout:build_folder_vars",
                                    default=[], check_type=list)
    ret = []
    for s in build_vars:
        tmp = None
        if s.startswith("settings."):
            _, var = s.split("settings.", 1)
            if var == "build_type":
                raise ConanException("Error, don't include 'settings.build_type' in the "
                                     "'tools.cmake.cmake_layout:build_folder_vars' conf. It is "
                                     "managed by default because 'CMakeToolchain' and 'CMakeDeps' "
                                     "are multi-config generators.`")
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
