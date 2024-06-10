import json
import os
import platform
import textwrap

from conan.api.output import ConanOutput, Color
from conan.tools.cmake.layout import get_build_folder_custom_vars
from conan.tools.cmake.toolchain.blocks import GenericSystemBlock
from conan.tools.cmake.utils import is_multi_configuration
from conan.tools.build import build_jobs
from conan.tools.microsoft import is_msvc
from conans.client.graph.graph import RECIPE_CONSUMER
from conan.errors import ConanException
from conans.util.files import save, load


def write_cmake_presets(conanfile, toolchain_file, generator, cache_variables,
                        user_presets_path=None, preset_prefix=None, buildenv=None, runenv=None,
                        cmake_executable=None, absolute_paths=None):
    preset_path, preset_data = _CMakePresets.generate(conanfile, toolchain_file, generator,
                                                      cache_variables, preset_prefix, buildenv, runenv,
                                                      cmake_executable, absolute_paths)
    _IncludingPresets.generate(conanfile, preset_path, user_presets_path, preset_prefix, preset_data,
                               absolute_paths)


class _CMakePresets:
    """ Conan generated main CMakePresets.json inside the generators_folder
    """
    @staticmethod
    def generate(conanfile, toolchain_file, generator, cache_variables, preset_prefix, buildenv, runenv,
                 cmake_executable, absolute_paths):
        toolchain_file = os.path.abspath(os.path.join(conanfile.generators_folder, toolchain_file))
        if not absolute_paths:
            try:  # Make it relative to the build dir if possible
                toolchain_file = os.path.relpath(toolchain_file, conanfile.build_folder)
            except ValueError:
                pass
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

        # In case user is injecting its own toolchain file, still need to locate generated CMakeDeps
        if conanfile.conf.get("tools.cmake.cmaketoolchain:toolchain_file"):
            build_paths = [conanfile.generators_folder]
            for req in conanfile.dependencies.values():
                cppinfo = req.cpp_info.aggregated_components()
                build_paths.extend(cppinfo.builddirs)
            build_paths = ";".join(p.replace("\\", "/") for p in build_paths)
            cache_variables["CMAKE_MODULE_PATH"] = build_paths
            cache_variables["CMAKE_PREFIX_PATH"] = build_paths

        preset_path = os.path.join(conanfile.generators_folder, "CMakePresets.json")
        multiconfig = is_multi_configuration(generator)
        if os.path.exists(preset_path):
            data = json.loads(load(preset_path))
            if "conan" not in data.get("vendor", {}):
                # The file is not ours, we cannot overwrite it
                raise ConanException("Existing CMakePresets.json not generated by Conan cannot be "
                                     "overwritten.\nUse --output-folder or define a 'layout' to "
                                     "avoid collision with your CMakePresets.json")
        if os.path.exists(preset_path) and multiconfig:
            data = json.loads(load(preset_path))
            build_preset = _CMakePresets._build_preset_fields(conanfile, multiconfig, preset_prefix)
            test_preset = _CMakePresets._test_preset_fields(conanfile, multiconfig, preset_prefix,
                                                            runenv)
            _CMakePresets._insert_preset(data, "buildPresets", build_preset)
            _CMakePresets._insert_preset(data, "testPresets", test_preset)
            configure_preset = _CMakePresets._configure_preset(conanfile, generator, cache_variables,
                                                               toolchain_file, multiconfig,
                                                               preset_prefix, buildenv,
                                                               cmake_executable)
            # Conan generated presets should have only 1 configurePreset, no more, overwrite it
            data["configurePresets"] = [configure_preset]
        else:
            data = _CMakePresets._contents(conanfile, toolchain_file, cache_variables, generator,
                                           preset_prefix, buildenv, runenv, cmake_executable)

        preset_content = json.dumps(data, indent=4)
        save(preset_path, preset_content)
        ConanOutput(str(conanfile)).info(f"CMakeToolchain generated: {preset_path}")
        return preset_path, data

    @staticmethod
    def _insert_preset(data, preset_type, preset):
        presets = data.setdefault(preset_type, [])
        preset_name = preset["name"]
        positions = [index for index, p in enumerate(presets) if p["name"] == preset_name]
        if positions:
            data[preset_type][positions[0]] = preset
        else:
            data[preset_type].append(preset)

    @staticmethod
    def _contents(conanfile, toolchain_file, cache_variables, generator, preset_prefix, buildenv,
                  runenv, cmake_executable):
        """
        Contents for the CMakePresets.json
        It uses schema version 3 unless it is forced to 2
        """
        multiconfig = is_multi_configuration(generator)
        conf = _CMakePresets._configure_preset(conanfile, generator, cache_variables, toolchain_file,
                                               multiconfig, preset_prefix, buildenv, cmake_executable)
        build = _CMakePresets._build_preset_fields(conanfile, multiconfig, preset_prefix)
        test = _CMakePresets._test_preset_fields(conanfile, multiconfig, preset_prefix, runenv)
        ret = {"version": 3,
               "vendor": {"conan": {}},
               "cmakeMinimumRequired": {"major": 3, "minor": 15, "patch": 0},
               "configurePresets": [conf],
               "buildPresets": [build],
               "testPresets": [test]
               }
        return ret

    @staticmethod
    def _configure_preset(conanfile, generator, cache_variables, toolchain_file, multiconfig,
                          preset_prefix, buildenv, cmake_executable):
        build_type = conanfile.settings.get_safe("build_type")
        name = _CMakePresets._configure_preset_name(conanfile, multiconfig)
        if preset_prefix:
            name = f"{preset_prefix}-{name}"
        if not multiconfig and build_type:
            cache_variables["CMAKE_BUILD_TYPE"] = build_type
        ret = {
            "name": name,
            "displayName": "'{}' config".format(name),
            "description": "'{}' configure using '{}' generator".format(name, generator),
            "generator": generator,
            "cacheVariables": cache_variables,
        }

        if buildenv:
            ret["environment"] = buildenv

        if cmake_executable:
            ret["cmakeExecutable"] = cmake_executable

        if is_msvc(conanfile):
            # We can force the generator Visual even if it is Ninja, to define the toolset
            toolset = GenericSystemBlock.get_toolset("Visual", conanfile)
            # It seems "external" strategy is enough, as it is defined by toolchain
            if toolset:
                ret["toolset"] = {
                    "value": toolset,
                    "strategy": "external"
                }
            arch = GenericSystemBlock.get_generator_platform("Visual", conanfile)
            # https://learn.microsoft.com/en-us/cpp/build/cmake-presets-vs
            if generator and "Ninja" in generator and arch == "Win32":
                arch = "x86"  # for command line, it is not Win32, it is x86
            if arch:
                ret["architecture"] = {
                    "value": arch,
                    "strategy": "external"
                }

        ret["toolchainFile"] = toolchain_file
        if conanfile.build_folder:
            # If we are installing a ref: "conan install <ref>", we don't have build_folder, because
            # we don't even have a conanfile with a `layout()` to determine the build folder.
            # If we install a local conanfile: "conan install ." with a layout(), it will be available.
            ret["binaryDir"] = conanfile.build_folder

        def _format_val(val):
            return f'"{val}"' if type(val) == str and " " in val else f"{val}"

        # https://github.com/conan-io/conan/pull/12034#issuecomment-1253776285
        cache_variables_info = " ".join(
            [f"-D{var}={_format_val(value)}" for var, value in cache_variables.items()])
        add_toolchain_cache = f"-DCMAKE_TOOLCHAIN_FILE={toolchain_file} " \
            if "CMAKE_TOOLCHAIN_FILE" not in cache_variables_info else ""

        try:
            is_consumer = conanfile._conan_node.recipe == RECIPE_CONSUMER and \
                          conanfile.tested_reference_str is None
        except:
            is_consumer = False
        if is_consumer:
            msg = textwrap.dedent(f"""\
                CMakeToolchain: Preset '{name}' added to CMakePresets.json.
                    (cmake>=3.23) cmake --preset {name}
                    (cmake<3.23) cmake <path> -G {_format_val(generator)} {add_toolchain_cache} {cache_variables_info}""")
            conanfile.output.info(msg, fg=Color.CYAN)
        return ret

    @staticmethod
    def _common_preset_fields(conanfile, multiconfig, preset_prefix):
        build_type = conanfile.settings.get_safe("build_type")
        configure_preset_name = _CMakePresets._configure_preset_name(conanfile, multiconfig)
        build_preset_name = _CMakePresets._build_and_test_preset_name(conanfile)
        if preset_prefix:
            configure_preset_name = f"{preset_prefix}-{configure_preset_name}"
            build_preset_name = f"{preset_prefix}-{build_preset_name}"
        ret = {"name": build_preset_name, "configurePreset": configure_preset_name}
        if multiconfig:
            ret["configuration"] = build_type
        return ret

    @staticmethod
    def _build_preset_fields(conanfile, multiconfig, preset_prefix):
        ret = _CMakePresets._common_preset_fields(conanfile, multiconfig, preset_prefix)
        build_preset_jobs = build_jobs(conanfile)
        ret["jobs"] = build_preset_jobs
        return ret

    @staticmethod
    def _test_preset_fields(conanfile, multiconfig, preset_prefix, runenv):
        ret = _CMakePresets._common_preset_fields(conanfile, multiconfig, preset_prefix)
        if runenv:
            ret["environment"] = runenv
        return ret

    @staticmethod
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

    @staticmethod
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


class _IncludingPresets:
    """
    CMakeUserPresets or ConanPresets.json that include the main generated CMakePresets
    """

    @staticmethod
    def generate(conanfile, preset_path, user_presets_path, preset_prefix, preset_data,
                 absolute_paths):
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
        inherited_user = {}
        if os.path.basename(user_presets_path) != "CMakeUserPresets.json":
            inherited_user = _IncludingPresets._collect_user_inherits(output_dir, preset_prefix)

        if not os.path.exists(user_presets_path):
            data = {"version": 4,
                    "vendor": {"conan": dict()}}
            for preset, inherits in inherited_user.items():
                for i in inherits:
                    data.setdefault(preset, []).append({"name": i})
        else:
            data = json.loads(load(user_presets_path))
            if "conan" not in data.get("vendor", {}):
                # The file is not ours, we cannot overwrite it
                return

        if inherited_user:
            _IncludingPresets._clean_user_inherits(data, preset_data)

        if not absolute_paths:
            try:  # Make it relative to the CMakeUserPresets.json if possible
                preset_path = os.path.relpath(preset_path, output_dir)
            except ValueError:
                pass
        data = _IncludingPresets._append_user_preset_path(data, preset_path, output_dir)

        data = json.dumps(data, indent=4)
        ConanOutput(str(conanfile)).info(f"CMakeToolchain generated: {user_presets_path}")
        save(user_presets_path, data)

    @staticmethod
    def _collect_user_inherits(output_dir, preset_prefix):
        # Collect all the existing targets in the user files, to create empty conan- presets
        # so things doesn't break for multi-platform, when inherits don't exist
        collected_targets = {}
        types = "configurePresets", "buildPresets", "testPresets"
        for file in ("CMakePresets.json", "CMakeUserPresets.json"):
            user_file = os.path.join(output_dir, file)
            if os.path.exists(user_file):
                user_json = json.loads(load(user_file))
                for preset_type in types:
                    for preset in user_json.get(preset_type, []):
                        inherits = preset.get("inherits", [])
                        if isinstance(inherits, str):
                            inherits = [inherits]
                        inherits = [i for i in inherits if i.startswith(preset_prefix)]
                        if inherits:
                            existing = collected_targets.setdefault(preset_type, [])
                            for i in inherits:
                                if i not in existing:
                                    existing.append(i)

        return collected_targets

    @staticmethod
    def _clean_user_inherits(data, preset_data):
        for preset_type in "configurePresets", "buildPresets", "testPresets":
            presets = preset_data.get(preset_type, [])
            presets_names = [p["name"] for p in presets]
            other = data.get(preset_type, [])
            other[:] = [p for p in other if p["name"] not in presets_names]

    @staticmethod
    def _append_user_preset_path(data, preset_path, output_dir):
        """ - Appends a 'include' to preset_path if the schema supports it.
            - Otherwise it merges to "data" all the configurePresets, buildPresets etc from the
              read preset_path.
        """
        if "include" not in data:
            data["include"] = []
        # Clear the folders that have been deleted
        data["include"] = [i for i in data.get("include", [])
                           if os.path.exists(os.path.join(output_dir, i))]
        if preset_path not in data["include"]:
            data["include"].append(preset_path)
        return data


def load_cmake_presets(folder):
    try:
        tmp = load(os.path.join(folder, "CMakePresets.json"))
    except FileNotFoundError:
        # Issue: https://github.com/conan-io/conan/issues/12896
        raise ConanException(f"CMakePresets.json was not found in {folder} folder. Check that you "
                             f"are using CMakeToolchain as generator to ensure its correct "
                             f"initialization.")
    return json.loads(tmp)
