import json
import os
import platform

from conans.util.files import save, load


def _contents(conanfile, toolchain_file, cache_variables, generator):
    return {"version": 3,
            "cmakeMinimumRequired": {"major": 3, "minor": 15, "patch": 0},
            "configurePresets": [{
                "name": "default",
                "displayName": "Default Config",
                "description": "Default configure using '{}' generator".format(generator),
                "generator": generator,
                "cacheVariables": cache_variables,
                "toolchainFile": toolchain_file,
                "binaryDir": conanfile.build_folder
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


def write_cmake_presets(conanfile, toolchain_file, generator):
    cache_variables = {}
    if platform.system() == "Windows" and generator == "MinGW Makefiles":
        cache_variables["CMAKE_SH"] = "CMAKE_SH-NOTFOUND"
        cmake_make_program = conanfile.conf.get("tools.gnu:make_program", default=None)
        if cmake_make_program:
            cmake_make_program = cmake_make_program.replace("\\", "/")
            cache_variables["CMAKE_MAKE_PROGRAM"] = cmake_make_program

    tmp = _contents(conanfile, toolchain_file, cache_variables, generator)
    tmp = json.dumps(tmp, indent=4)
    save(os.path.join(conanfile.generators_folder, "CMakePresets.json"), tmp)


def load_cmake_presets(folder):
    tmp = load(os.path.join(folder, "CMakePresets.json"))
    return json.loads(tmp)
