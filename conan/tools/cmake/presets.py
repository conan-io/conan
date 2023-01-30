import json
import os
import platform

from conan.tools.cmake.layout import get_build_folder_custom_vars
from conan.tools.cmake.utils import is_multi_configuration
from conan.tools.microsoft import is_msvc
from conans.errors import ConanException
from conans.util.files import save, load


def _build_and_test_preset_fields(conanfile, multiconfig):
    build_type = conanfile.settings.get_safe("build_type")
    configure_preset_name = _configure_preset_name(conanfile, multiconfig)
    build_preset_name = _build_and_test_preset_name(conanfile)
    ret = {"name": build_preset_name,
           "configurePreset": configure_preset_name}
    if multiconfig:
        ret["configuration"] = build_type
    return ret


def _build_and_test_preset_name(conanfile):
    build_type = conanfile.settings.get_safe("build_type")
    custom_conf, user_defined_build = get_build_folder_custom_vars(conanfile)
    if user_defined_build:
        return custom_conf

    if custom_conf:
        if build_type:
            return "{}-{}".format(custom_conf, build_type.lower())
        else:
            return custom_conf
    return build_type.lower() if build_type else "default"


def _configure_preset_name(conanfile, multiconfig):
    build_type = conanfile.settings.get_safe("build_type")
    custom_conf, user_defined_build = get_build_folder_custom_vars(conanfile)

    if user_defined_build:
        return custom_conf

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


def _insert_preset(data, preset_name, preset):
    position = _get_already_existing_preset_index(preset["name"], data.setdefault(preset_name, []))
    if position is not None:
        data[preset_name][position] = preset
    else:
        data[preset_name].append(preset)


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
    multiconfig = is_multi_configuration(generator)
    conf = _configure_preset(conanfile, generator, cache_variables, toolchain_file, multiconfig)
    build = _build_and_test_preset_fields(conanfile, multiconfig)
    ret = {"version": _schema_version(conanfile, default=3),
           "vendor": {"conan": {}},
           "cmakeMinimumRequired": {"major": 3, "minor": 15, "patch": 0},
           "configurePresets": [conf],
           "buildPresets": [build],
           "testPresets": [build]
           }
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
    if os.path.exists(preset_path) and multiconfig:
        data = json.loads(load(preset_path))
        build_preset = _build_and_test_preset_fields(conanfile, multiconfig)
        _insert_preset(data, "buildPresets", build_preset)
        _insert_preset(data, "testPresets", build_preset)
        configure_preset = _configure_preset(conanfile, generator, cache_variables, toolchain_file,
                                             multiconfig)
        # Conan generated presets should have only 1 configurePreset, no more, overwrite it
        data["configurePresets"] = [configure_preset]
    else:
        data = _contents(conanfile, toolchain_file, cache_variables, generator)

    preset_content = json.dumps(data, indent=4)
    save(preset_path, preset_content)
    _save_cmake_user_presets(conanfile, preset_path, user_presets_path)


def _save_cmake_user_presets(conanfile, preset_path, user_presets_path):
    if not user_presets_path:
        return

    # If generators folder is the same as source folder, do not create the user presets
    # we already have the CMakePresets.json right there
    if not (conanfile.source_folder and conanfile.source_folder != conanfile.generators_folder):
        return

    user_presets_path = os.path.join(conanfile.source_folder, user_presets_path)
    if os.path.isdir(user_presets_path):  # Allows user to specify only the folder
        output_dir = user_presets_path
        user_presets_path = os.path.join(user_presets_path, "CMakeUserPresets.json")
    else:
        output_dir = os.path.dirname(user_presets_path)

    if not os.path.exists(os.path.join(output_dir, "CMakeLists.txt")):
        return

    # It uses schema version 4 unless it is forced to 2
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
