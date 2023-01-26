import os
import shutil
from pathlib import Path

from conans.errors import ConanException
from conans.model.ref import ConanFileReference
from conans.util.sha import sha1


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
    test_root_build_folder = get_root_test_build_folder(conanfile)  # only for test_package's
    config_build_folder, user_defined_build = get_build_folder_custom_vars(conanfile)

    if config_build_folder:
        build_folder = os.path.join(test_root_build_folder, build_folder, config_build_folder)
    if not multi and not user_defined_build:
        build_folder = os.path.join(test_root_build_folder, build_folder, build_type)

    conanfile.folders.build = build_folder
    conanfile.folders.generators = os.path.join(conanfile.folders.build, "generators")
    conanfile.cpp.source.includedirs = ["include"]

    if multi and not user_defined_build:
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
        group, var = s.split(".", 1)
        tmp = None
        if group == "settings":
            tmp = conanfile.settings.get_safe(var)
        elif group == "options":
            value = conanfile.options.get_safe(var)
            if value is not None:
                tmp = "{}_{}".format(var, value)
        else:
            raise ConanException("Invalid 'tools.cmake.cmake_layout:build_folder_vars' value, it has"
                                 " to start with 'settings.' or 'options.': {}".format(s))
        if tmp:
            ret.append(tmp.lower())

    user_defined_build = "settings.build_type" in build_vars
    return "-".join(ret), user_defined_build


def get_root_test_build_folder(conanfile):
    """
    Get a different root test build folder path (or the test_package/ one) if
    tools.cmake.cmake_layout:test_build_folder is specified.

    If specified the test output build folder could look like this:

    >> [TEST_ROOT_PATH]/test_output-[BUILD_TYPE]_[COMPILER]_[COMPILER_VERSION]-[SHA1]

    Several notes:

        * tools.cmake.cmake_layout:test_build_folder=recipe_folder indicates that the root path
          will be the test_package/ by default (as usual).
        * tools.cmake.cmake_layout:test_build_folder=MY_FOLDER/ will add to the test build folder
          name the [REF_NAME]_[REF_VERSION] as prefix, so it could look like:
          >> [TEST_ROOT_PATH]/[REF_NAME]_[REF_VERSION]-test_output-[BUILD_TYPE]_[COMPILER]_[COMPILER_VERSION]-[SHA1]
        * If tools.cmake.cmake_layout:test_build_folder is not specified, it will work as usual.
    """
    # Get root build folder from global.conf or profile
    test_build_root_folder = conanfile.conf.get("tools.cmake.cmake_layout:test_build_folder",
                                                check_type=str)
    tested_reference = conanfile.tested_reference_str
    # FIXME: Should we have a better way to check that?
    if tested_reference is None or test_build_root_folder is None:
        return ''

    if test_build_root_folder.lower() != "recipe_folder":
        ref = ConanFileReference.loads(tested_reference)
        prefix = f"{ref.name}_{ref.version}-test_output"
    else:
        # Assuming that it's called under the test_package folder
        test_build_root_folder = conanfile.recipe_folder
        prefix = 'test_output'

    settings = conanfile.settings.values.dumps()
    # FIXME: Conan 1.x: they are changing in the first call so the SHA is changing... Check Conan 2.x
    # options = conanfile.options.values.dumps()
    conf = conanfile.conf.dumps()
    suffix = sha1((settings + conf).encode())
    # Hardcoded fields to add to the prefix
    settings_fields = ["build_type", "compiler", "compiler.version"]
    settings_values = "_".join([conanfile.settings.get_safe(f, '') for f in settings_fields])
    test_build_folder = os.path.join(test_build_root_folder, f"{prefix}-{settings_values}-{suffix}")
    return test_build_folder
