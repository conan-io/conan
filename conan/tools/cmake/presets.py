import json
import os
import platform

from conans.util.files import save, load


def _contents(conanfile, toolchain_file, cache_variables, generator):
    ret = {"version": 3,
           "cmakeMinimumRequired": {"major": 3, "minor": 15, "patch": 0},
           "configurePresets": [{
                "name": "default",
                "displayName": "Default Config",
                "description": "Default configure using '{}' generator".format(generator),
                "generator": generator,
                "cacheVariables": cache_variables,
                "toolchainFile": toolchain_file,
           }],
           "buildPresets": [{
              "name": "default",
              "configurePreset": "default"
           }],
           "testPresets": [{
              "name": "default",
              "configurePreset": "default"
           }]
          }
    if conanfile.build_folder:
        # If we are installing a ref: "conan install <ref>", we don't have build_folder, because
        # we don't even have a conanfile with a `layout()` to determine the build folder.
        # If we install a local conanfile: "conan install ." with a layout(), it will be available.
        ret["configurePresets"][0]["binaryDir"] = conanfile.build_folder
    return ret


def write_cmake_presets(conanfile, toolchain_file, generator):
    cache_variables = {}
    # We no longer need variables in presets, as they are defined in CMAKE_PROJECT_INCLUDE
    tmp = _contents(conanfile, toolchain_file, cache_variables, generator)
    tmp = json.dumps(tmp, indent=4)
    save(os.path.join(conanfile.generators_folder, "CMakePresets.json"), tmp)


def load_cmake_presets(folder):
    tmp = load(os.path.join(folder, "CMakePresets.json"))
    return json.loads(tmp)
