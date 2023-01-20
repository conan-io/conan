import datetime
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
    config_build_folder, user_defined_build = get_build_folder_custom_vars(conanfile)
    if config_build_folder:
        build_folder = os.path.join(build_folder, config_build_folder)
    if not multi and not user_defined_build:
        build_folder = os.path.join(build_folder, build_type)
    conanfile.folders.build = build_folder

    conanfile.folders.generators = os.path.join(conanfile.folders.build, "generators")

    conanfile.cpp.source.includedirs = ["include"]

    if multi and not user_defined_build:
        conanfile.cpp.build.libdirs = ["{}".format(build_type)]
        conanfile.cpp.build.bindirs = ["{}".format(build_type)]
    else:
        conanfile.cpp.build.libdirs = ["."]
        conanfile.cpp.build.bindirs = ["."]


def _calculate_build_vars(conanfile, build_vars):
    configuration_discriminant = []
    for config in build_vars:
        group, var = config.split(".", 1)
        if group == "settings":
            value = conanfile.settings.get_safe(var)
        elif group == "options":
            value = conanfile.options.get_safe(var)
            if value is None:
                continue
        else:
            raise ConanException("Invalid build_folder_vars value, it has to start with "
                                 f"'settings.' or 'options.': {config}")
        configuration_discriminant.append(f"{config}_{value}".lower())
    return configuration_discriminant


def get_build_folder_custom_vars(conanfile):
    if conanfile.tested_reference_str is None:
        build_vars = conanfile.conf.get("tools.cmake.cmake_layout:build_folder_vars",
                                        default=[], check_type=list)
        ret = _calculate_build_vars(conanfile, build_vars)
        user_defined_build = "settings.build_type" in build_vars
        return "-".join(ret), user_defined_build
    # Check if maybe test_type is a better flag for this?
    else:
        # Get root build folder from global.conf
        test_build_root_folder = conanfile.conf.get("user.test_build_folder", check_type=str,
                                                    default=".")
        # Start the folder path with something common, so it can get ignored programmatically
        test_build_folder = os.path.join(test_build_root_folder, "test_output")
        # Get each config and create a name based on their values

        test_build_settings = [f"settings.{setting}" for setting in conanfile.settings.fields]
        configuration_discriminant = _calculate_build_vars(conanfile, test_build_settings)
        # Append a timestamp/counter
        configuration_discriminant.append(datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S%f"))
        return os.path.join(test_build_folder, "-".join(configuration_discriminant)), True



