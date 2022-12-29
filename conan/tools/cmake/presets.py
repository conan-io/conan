import json
import os
import platform

from conan.tools.cmake.layout import get_build_folder_custom_vars
from conan.tools.cmake.utils import is_multi_configuration
from conan.tools.microsoft import is_msvc
from conans.errors import ConanException
from conans.util.files import save, load


def _build_preset(conanfile, multiconfig):
    build_type = conanfile.settings.get_safe("build_type")
    configure_preset_name = _configure_preset_name(conanfile, multiconfig)
    ret = {"name": _build_preset_name(conanfile),
           "configurePreset": configure_preset_name}
    if multiconfig:
        ret["configuration"] = build_type
    return ret


def _build_preset_name(conanfile):
    build_type = conanfile.settings.get_safe("build_type")
    custom_conf = get_build_folder_custom_vars(conanfile)
    if custom_conf:
        if build_type:
            return "{}-{}".format(custom_conf, build_type.lower())
        else:
            return custom_conf
    return build_type.lower() if build_type else "default"


def _configure_preset_name(conanfile, multiconfig):
    build_type = conanfile.settings.get_safe("build_type")
    custom_conf = get_build_folder_custom_vars(conanfile)

    if multiconfig or not build_type:
        return "default" if not custom_conf else custom_conf

    if custom_conf:
        return "{}-{}".format(custom_conf, str(build_type).lower())
    else:
        return str(build_type).lower()


def _configure_preset(conanfile, generator, cache_variables, toolchain_file, multiconfig):
    build_type = conanfile.settings.get_safe("build_type")
    name = _configure_preset_name(conanfile, multiconfig)
    if not multiconfig and build_type:
        cache_variables["CMAKE_BUILD_TYPE"] = build_type
    ret = {
            "name": name,
            "displayName": "'{}' config".format(name),
            "description": "'{}' configure using '{}' generator".format(name, generator),
            "generator": generator,
            "cacheVariables": cache_variables,
           }
    if "Ninja" in generator and is_msvc(conanfile):
        toolset_arch = conanfile.conf.get("tools.cmake.cmaketoolchain:toolset_arch")
        if toolset_arch:
            toolset_arch = "host={}".format(toolset_arch)
            ret["toolset"] = {
                "value": toolset_arch,
                "strategy": "external"
            }
        arch = {"x86": "x86",
                "x86_64": "x64",
                "armv7": "ARM",
                "armv8": "ARM64"}.get(conanfile.settings.get_safe("arch"))

        if arch:
            ret["architecture"] = {
                "value": arch,
                "strategy": "external"
            }

    if not _forced_schema_2(conanfile):
        ret["toolchainFile"] = toolchain_file
    else:
        ret["cacheVariables"]["CMAKE_TOOLCHAIN_FILE"] = toolchain_file

    if conanfile.build_folder:
        # If we are installing a ref: "conan install <ref>", we don't have build_folder, because
        # we don't even have a conanfile with a `layout()` to determine the build folder.
        # If we install a local conanfile: "conan install ." with a layout(), it will be available.
        ret["binaryDir"] = conanfile.build_folder

    def _format_val(val):
        return f'"{val}"' if type(val) == str and " " in val else f"{val}"

    # https://github.com/conan-io/conan/pull/12034#issuecomment-1253776285
    cache_variables_info = " ".join([f"-D{var}={_format_val(value)}" for var, value in cache_variables.items()])
    add_toolchain_cache = f"-DCMAKE_TOOLCHAIN_FILE={toolchain_file} " \
        if "CMAKE_TOOLCHAIN_FILE" not in cache_variables_info else ""

    conanfile.output.info(f"Preset '{name}' added to CMakePresets.json. Invoke it manually using "
                          f"'cmake --preset {name}'")
    conanfile.output.info(f"If your CMake version is not compatible with "
                          f"CMakePresets (<3.19) call cmake like: 'cmake <path> "
                          f"-G {_format_val(generator)} {add_toolchain_cache}"
                          f"{cache_variables_info}'")
    return ret


def _forced_schema_2(conanfile):
    version = conanfile.conf.get("tools.cmake.cmaketoolchain.presets:max_schema_version",
                                 check_type=int)
    if not version:
        return False

    if version < 2:
        raise ConanException("The minimum value for 'tools.cmake.cmaketoolchain.presets:"
                             "schema_version' is 2")
    if version < 4:
        return True

    return False


def _schema_version(conanfile, default):
    if _forced_schema_2(conanfile):
        return 2

    return default


def _contents(conanfile, toolchain_file, cache_variables, generator):
    """
    Contents for the CMakePresets.json
    It uses schema version 3 unless it is forced to 2
    """
    ret = {"version": _schema_version(conanfile, default=3),
           "cmakeMinimumRequired": {"major": 3, "minor": 15, "patch": 0},
           "configurePresets": [],
           "buildPresets": [],
           "testPresets": []
          }
    multiconfig = is_multi_configuration(generator)
    ret["buildPresets"].append(_build_preset(conanfile, multiconfig))
    _conf = _configure_preset(conanfile, generator, cache_variables, toolchain_file, multiconfig)
    ret["configurePresets"].append(_conf)
    return ret


def write_cmake_presets(conanfile, toolchain_file, generator, cache_variables,
                        user_presets_path=None):
    cache_variables = cache_variables or {}
    if platform.system() == "Windows" and generator == "MinGW Makefiles":
        if "CMAKE_SH" not in cache_variables:
            cache_variables["CMAKE_SH"] = "CMAKE_SH-NOTFOUND"

        cmake_make_program = conanfile.conf.get("tools.gnu:make_program",
                                                default=cache_variables.get("CMAKE_MAKE_PROGRAM"))
        if cmake_make_program:
            cmake_make_program = cmake_make_program.replace("\\", "/")
            cache_variables["CMAKE_MAKE_PROGRAM"] = cmake_make_program

    if "CMAKE_POLICY_DEFAULT_CMP0091" not in cache_variables:
        cache_variables["CMAKE_POLICY_DEFAULT_CMP0091"] = "NEW"

    if "BUILD_TESTING" not in cache_variables:
        if conanfile.conf.get("tools.build:skip_test", check_type=bool):
            cache_variables["BUILD_TESTING"] = "OFF"

    preset_path = os.path.join(conanfile.generators_folder, "CMakePresets.json")
    multiconfig = is_multi_configuration(generator)

    if os.path.exists(preset_path):
        data = json.loads(load(preset_path))
        build_preset = _build_preset(conanfile, multiconfig)
        position = _get_already_existing_preset_index(build_preset["name"], data["buildPresets"])
        if position is not None:
            data["buildPresets"][position] = build_preset
        else:
            data["buildPresets"].append(build_preset)

        configure_preset = _configure_preset(conanfile, generator, cache_variables, toolchain_file,
                                             multiconfig)
        position = _get_already_existing_preset_index(configure_preset["name"],
                                                      data["configurePresets"])
        if position is not None:
            data["configurePresets"][position] = configure_preset
        else:
            data["configurePresets"].append(configure_preset)
    else:
        data = _contents(conanfile, toolchain_file, cache_variables, generator)

    data = json.dumps(data, indent=4)
    save(preset_path, data)
    save_cmake_user_presets(conanfile, preset_path, user_presets_path)


def save_cmake_user_presets(conanfile, preset_path, user_presets_path=None):
    if user_presets_path is False:
        return

    # Try to save the CMakeUserPresets.json if layout declared and CMakeLists.txt found
    if conanfile.source_folder and conanfile.source_folder != conanfile.generators_folder:
        if user_presets_path:
            output_dir = os.path.join(conanfile.source_folder, user_presets_path) \
                if not os.path.isabs(user_presets_path) else user_presets_path
        else:
            output_dir = conanfile.source_folder

        if user_presets_path or os.path.exists(os.path.join(output_dir, "CMakeLists.txt")):
            """
                Contents for the CMakeUserPresets.json
                It uses schema version 4 unless it is forced to 2
            """
            user_presets_path = os.path.join(output_dir, "CMakeUserPresets.json")
            if not os.path.exists(user_presets_path):
                data = {"version": _schema_version(conanfile, default=4),
                        "vendor": {"conan": dict()}}
            else:
                data = json.loads(load(user_presets_path))
                if "conan" not in data.get("vendor", {}):
                    # The file is not ours, we cannot overwrite it
                    return
            data = _append_user_preset_path(conanfile, data, preset_path)
            data = json.dumps(data, indent=4)
            save(user_presets_path, data)


def _get_already_existing_preset_index(name, presets):
    """Get the index of a Preset with a given name, this is used to replace it with updated contents
    """
    positions = [index for index, p in enumerate(presets)
                 if p["name"] == name]
    if positions:
        return positions[0]
    return None


def _append_user_preset_path(conanfile, data, preset_path):
    """ - Appends a 'include' to preset_path if the schema supports it.
        - Otherwise it merges to "data" all the configurePresets, buildPresets etc from the
          read preset_path.
    """
    if not _forced_schema_2(conanfile):
        if "include" not in data:
            data["include"] = []
        # Clear the folders that have been deleted
        data["include"] = [i for i in data.get("include", []) if os.path.exists(i)]
        if preset_path not in data["include"]:
            data["include"].append(preset_path)
        return data
    else:
        # Merge the presets
        cmake_preset = json.loads(load(preset_path))
        for preset_type in ("configurePresets", "buildPresets", "testPresets"):
            for preset in cmake_preset.get(preset_type, []):
                if preset_type not in data:
                    data[preset_type] = []

                position = _get_already_existing_preset_index(preset["name"], data[preset_type])
                if position is not None:
                    # If the preset already existed, replace the element with the new one
                    data[preset_type][position] = preset
                else:
                    data[preset_type].append(preset)
        return data


def load_cmake_presets(folder):
    tmp = load(os.path.join(folder, "CMakePresets.json"))
    return json.loads(tmp)


def get_configure_preset(cmake_presets, conanfile):
    expected_name = _configure_preset_name(conanfile, multiconfig=False)
    # Do we find a preset for the current configuration?
    for preset in cmake_presets["configurePresets"]:
        if preset["name"] == expected_name:
            return preset

    expected_name = _configure_preset_name(conanfile, multiconfig=True)
    # In case of multi-config generator or None build_type
    for preset in cmake_presets["configurePresets"]:
        if preset["name"] == expected_name:
            return preset

    # FIXME: Might be an issue if someone perform several conan install that involves different
    #        CMake generators (multi and single config). Would be impossible to determine which
    #        is the correct configurePreset because the generator IS in the configure preset.

    raise ConanException("Not available configurePreset, expected name is {}".format(expected_name))
