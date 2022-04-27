import json
import os
import platform

from conan.tools.cmake.utils import is_multi_configuration
from conans.util.files import save, load


def _add_build_preset(conanfile, multiconfig):
    build_type = conanfile.settings.get_safe("build_type")
    ret = {"name": "Build {}".format(build_type),
           "configurePreset": "default"}
    if multiconfig:
        ret["configuration"] = build_type
    return ret


def _add_configure_preset(conanfile, generator, cache_variables, toolchain_file, multiconfig):
    build_type = conanfile.settings.get_safe("build_type")
    name = "default" if not build_type or multiconfig else build_type
    if not multiconfig:
        cache_variables["CMAKE_BUILD_TYPE"] = build_type
    ret = {
            "name": name,
            "displayName": "{} Config".format(name.capitalize()),
            "description": "{} configure using '{}' generator".format(name.capitalize(), generator),
            "generator": generator,
            "cacheVariables": cache_variables,
            "toolchainFile": toolchain_file,
           }
    if conanfile.build_folder:
        # If we are installing a ref: "conan install <ref>", we don't have build_folder, because
        # we don't even have a conanfile with a `layout()` to determine the build folder.
        # If we install a local conanfile: "conan install ." with a layout(), it will be available.
        ret["binaryDir"] = conanfile.build_folder
    return ret


def _contents(conanfile, toolchain_file, cache_variables, generator):
    ret = {"version": 3,
           "cmakeMinimumRequired": {"major": 3, "minor": 15, "patch": 0},
           "configurePresets": [],
           "buildPresets": [],
           "testPresets": [{
              "name": "default",
              "configurePreset": "default"
           }]
          }
    multiconfig = is_multi_configuration(generator)
    ret["buildPresets"].append(_add_build_preset(conanfile, multiconfig))
    _conf = _add_configure_preset(conanfile, generator, cache_variables, toolchain_file, multiconfig)
    ret["configurePresets"].append(_conf)
    return ret


def write_cmake_presets(conanfile, toolchain_file, generator):
    cache_variables = {}
    if platform.system() == "Windows" and generator == "MinGW Makefiles":
        cache_variables["CMAKE_SH"] = "CMAKE_SH-NOTFOUND"
        cmake_make_program = conanfile.conf.get("tools.gnu:make_program", default=None)
        if cmake_make_program:
            cmake_make_program = cmake_make_program.replace("\\", "/")
            cache_variables["CMAKE_MAKE_PROGRAM"] = cmake_make_program
    cache_variables["CMAKE_POLICY_DEFAULT_CMP0091"] = "NEW"

    preset_path = os.path.join(conanfile.generators_folder, "CMakePresets.json")
    multiconfig = is_multi_configuration(generator)
    build_type = conanfile.settings.get_safe("build_type")
    if multiconfig and os.path.exists(preset_path):
        # We append the new configuration making sure that we don't overwrite it
        data = json.loads(load(preset_path))
        build_presets = data["buildPresets"]
        already_exist = any([b["configuration"] for b in build_presets if b == build_type])
        if not already_exist:
            data["buildPresets"].append(_add_build_preset(conanfile, multiconfig))
    else:
        data = _contents(conanfile, toolchain_file, cache_variables, generator)

    data = json.dumps(data, indent=4)
    save(preset_path, data)


def load_cmake_presets(folder):
    tmp = load(os.path.join(folder, "CMakePresets.json"))
    return json.loads(tmp)
