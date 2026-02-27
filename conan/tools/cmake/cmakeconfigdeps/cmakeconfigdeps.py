import glob
import os
import re
import textwrap

from jinja2 import Template

from conan.api.output import Color, ConanOutput
from conan.errors import ConanException
from conan.internal import check_duplicated_generator
from conan.internal.api.install.generators import relativize_path
from conan.internal.model.dependencies import get_transitive_requires
from conan.tools.cmake.cmakeconfigdeps.config import ConfigTemplate2
from conan.tools.cmake.cmakeconfigdeps.config_version import ConfigVersionTemplate2
from conan.tools.cmake.cmakeconfigdeps.target_configuration import TargetConfigurationTemplate2
from conan.tools.cmake.cmakeconfigdeps.targets import TargetsTemplate2
from conan.tools.files import save
from conan.internal.util.files import load

FIND_MODE_MODULE = "module"
FIND_MODE_CONFIG = "config"
FIND_MODE_NONE = "none"
FIND_MODE_BOTH = "both"


class CMakeConfigDeps:

    def __init__(self, conanfile):
        """
        :param conanfile: ``< ConanFile object >`` The current recipe object. Always use ``self``.
        """
        self._conanfile = conanfile
        self.configuration = str(self._conanfile.settings.build_type)

        # These are just for legacy compatibility, but not use at al
        self._build_context_activated = []
        self._build_context_build_modules = []
        self._build_context_suffix = {}
        # Enable/Disable checking if a component target exists or not
        self._check_components_exist = False

        self._properties = {}

    @property
    def build_context_activated(self):
        return self._build_context_activated

    @build_context_activated.setter
    def build_context_activated(self, value):
        self._conanfile.output.warning("CMakeConfigDeps.build_context_activated is deprecated, "
                                       "not used anymore", warn_tag="deprecated")
        self._build_context_activated = value

    @property
    def build_context_build_modules(self):
        return self._build_context_build_modules

    @build_context_build_modules.setter
    def build_context_build_modules(self, value):
        self._conanfile.output.warning("CMakeConfigDeps.build_context_build_modules is deprecated, "
                                       "not used anymore", warn_tag="deprecated")
        self._build_context_build_modules = value

    @property
    def build_context_suffix(self):
        return self._build_context_suffix

    @build_context_suffix.setter
    def build_context_suffix(self, value):
        self._conanfile.output.warning("CMakeConfigDeps.build_context_suffix is deprecated, "
                                       "not used anymore", warn_tag="deprecated")
        self._build_context_suffix = value

    @property
    def check_components_exist(self):
        return self._check_components_exist

    @check_components_exist.setter
    def check_components_exist(self, value):
        self._conanfile.output.warning("CMakeConfigDeps.check_components_exist is deprecated, "
                                       "not used anymore", warn_tag="deprecated")
        self._check_components_exist = value

    def generate(self):
        """
        This method will save the generated files to the ``conanfile.generators_folder`` folder
        """
        self._conanfile.output.warning("CMakeConfigDeps is experimental, and might get "
                                       "breaking changes in future releases",
                                       warn_tag="experimental")
        check_duplicated_generator(self, self._conanfile)
        # Current directory is the generators_folder
        generator_files = self._content()
        for generator_file, content in generator_files.items():
            save(self._conanfile, generator_file, content)
        _PathGenerator(self, self._conanfile).generate()

    def _content(self):
        host_req = self._conanfile.dependencies.host
        build_req = self._conanfile.dependencies.direct_build
        test_req = self._conanfile.dependencies.test

        # Iterate all the transitive requires
        ret = {}
        direct_deps = []
        for require, dep in list(host_req.items()) + list(build_req.items()) + list(test_req.items()):
            cmake_find_mode = self.get_property("cmake_find_mode", dep)
            cmake_find_mode = cmake_find_mode or FIND_MODE_CONFIG
            cmake_find_mode = cmake_find_mode.lower()
            if cmake_find_mode == FIND_MODE_NONE:
                continue
            if cmake_find_mode in (FIND_MODE_MODULE, FIND_MODE_BOTH):
                ConanOutput(self._conanfile.ref).warning("CMakeConfigDeps does not support "
                                                         f"module find mode in {dep}.\n"
                                                         f"Config mode will be used regardless.",
                                                         # Should this be risk?
                                                         warn_tag="deprecated")

            if require.direct:
                direct_deps.append((require, dep))
            full_cpp_info = dep.cpp_info.deduce_full_cpp_info(dep)
            config = ConfigTemplate2(self, require, dep, full_cpp_info)
            ret[config.filename] = config.content()
            config_version = ConfigVersionTemplate2(self, dep)
            ret[config_version.filename] = config_version.content()

            targets = TargetsTemplate2(self, dep)
            ret[targets.filename] = targets.content()
            target_configuration = TargetConfigurationTemplate2(self, dep, require, full_cpp_info)
            ret[target_configuration.filename] = target_configuration.content()

        self._print_help(direct_deps)
        return ret

    def _print_help(self, direct_deps):
        if direct_deps:
            msg = ["CMakeDeps necessary find_package() and targets for your CMakeLists.txt"]
            link_targets = []
            for (require, dep) in direct_deps:
                note = " # Optional. This is a tool-require, can't link its targets" \
                    if require.build else ""
                msg.append(f"    find_package({self.get_cmake_filename(dep)}){note}")
                if not require.build and not dep.cpp_info.exe:
                    target_name = self.get_property("cmake_target_name", dep)
                    link_targets.append(target_name or f"{dep.ref.name}::{dep.ref.name}")
            if link_targets:
                msg.append(f"    target_link_libraries(... {' '.join(link_targets)})")
            self._conanfile.output.info("\n".join(msg), fg=Color.CYAN)

    def set_property(self, dep, prop, value, build_context=False):
        """
        Using this method you can overwrite the :ref:`property<CMakeConfigDeps Properties>` values
        set by the Conan recipes from the consumer.

        :param dep: Name of the dependency to set the :ref:`property<CMakeConfigDeps Properties>`.
         For components use the syntax: ``dep_name::component_name``.
        :param prop: Name of the :ref:`property<CMakeDeps Properties>`.
        :param value: Value of the property. Use ``None`` to invalidate any value set by the
         upstream recipe.
        :param build_context: Set to ``True`` if you want to set the property for a dependency that
         belongs to the build context (``False`` by default).
        """
        build_suffix = "&build" if build_context else ""
        self._properties.setdefault(f"{dep}{build_suffix}", {}).update({prop: value})

    def get_property(self, prop, dep, comp_name=None, check_type=None):
        dep_name = dep.ref.name
        build_suffix = "&build" if dep.context == "build" else ""
        dep_comp = f"{str(dep_name)}::{comp_name}" if comp_name else f"{str(dep_name)}"
        try:
            value = self._properties[f"{dep_comp}{build_suffix}"][prop]
            if check_type is not None and not isinstance(value, check_type):
                raise ConanException(f'The expected type for {prop} is "{check_type.__name__}", '
                                     f'but "{type(value).__name__}" was found')
            return value
        except KeyError:
            # Here we are not using the cpp_info = deduce_cpp_info(dep) because it is not
            # necessary for the properties
            if not comp_name:
                return dep.cpp_info.get_property(prop, check_type=check_type)
            comp = dep.cpp_info.components.get(comp_name)  # it is a default dict
            if comp is not None:
                return comp.get_property(prop, check_type=check_type)

    def get_cmake_filename(self, dep):
        # Get the name of the file for the find_package(XXX)
        # This is used by CMakeDeps to determine:
        # - The filename to generate (XXX-config.cmake or FindXXX.cmake)
        # - The name of the defined XXX_DIR variables
        # - The name of transitive dependencies for calls to find_dependency
        ret = self.get_property("cmake_file_name", dep)
        return ret or dep.ref.name

    def _get_find_mode(self, dep):
        tmp = self.get_property("cmake_find_mode", dep)
        if tmp is None:
            return "config"
        return tmp.lower()

    def get_transitive_requires(self, conanfile):
        # Prepared to filter transitive tool-requires with visible=True
        return get_transitive_requires(self._conanfile, conanfile)


# TODO: Repeated from CMakeToolchain blocks
def _join_paths(conanfile, paths):
    paths = [p.replace('\\', '/').replace('$', '\\$').replace('"', '\\"') for p in paths]
    paths = [relativize_path(p, conanfile, "${CMAKE_CURRENT_LIST_DIR}") for p in paths]
    return " ".join([f'"{p}"' for p in paths])


class _PathGenerator:
    _conan_cmakedeps_paths = "conan_cmakedeps_paths.cmake"

    def __init__(self, cmakedeps, conanfile):
        self._conanfile = conanfile
        self._cmakedeps = cmakedeps

    def _get_cmake_paths(self, requirements, dirs_name):
        paths = {}
        cmake_vars = {
            "bindirs": "CMAKE_PROGRAM_PATH",
            "libdirs": "CMAKE_LIBRARY_PATH",
            "includedirs": "CMAKE_INCLUDE_PATH",
            "frameworkdirs": "CMAKE_FRAMEWORK_PATH",
            "builddirs": "CMAKE_MODULE_PATH"
        }
        for req, dep in requirements:
            cppinfo = dep.cpp_info.aggregated_components()
            cppinfo_dirs = getattr(cppinfo, dirs_name, [])
            if not cppinfo_dirs:
                continue
            previous = paths.get(req.ref.name)
            if previous:
                self._conanfile.output.info(f"There is already a '{req.ref}' package contributing"
                                            f" to {cmake_vars[dirs_name]}. Using the one"
                                            f" defined by the context={dep.context}.")
            paths[req.ref.name] = cppinfo_dirs
        return [d for dirs in paths.values() for d in dirs]

    def generate(self):
        template = textwrap.dedent("""\
        set(CMAKE_FIND_PACKAGE_PREFER_CONFIG ON)

        {% for pkg_name, folder in pkg_paths.items() %}
        set({{pkg_name}}_DIR "{{folder}}")
        {% endfor %}
        {% for pkg_name, folders in pkg_paths_multi.items() %}
        {% for folder in folders %}
        list(APPEND CONAN_{{pkg_name}}_DIR_MULTI "{{folder}}")
        {% endfor %}
        {% endfor %}
        {% if host_runtime_dirs %}
        set(CONAN_RUNTIME_LIB_DIRS {{ host_runtime_dirs }} )
        # Only for VS, needs CMake>=3.27
        set(CMAKE_VS_DEBUGGER_ENVIRONMENT "PATH=${CONAN_RUNTIME_LIB_DIRS};%PATH%")
        {% endif %}
        {% if cmake_program_path %}
        list(PREPEND CMAKE_PROGRAM_PATH {{ cmake_program_path }})
        {% endif %}
        {% if cmake_library_path %}
        list(PREPEND CMAKE_LIBRARY_PATH {{ cmake_library_path }})
        {% endif %}
        {% if cmake_include_path %}
        list(PREPEND CMAKE_INCLUDE_PATH {{ cmake_include_path }})
        {% endif %}
        {% if cmake_framework_path %}
        list(PREPEND CMAKE_FRAMEWORK_PATH {{ cmake_framework_path }})
        {% endif %}
        # Definition of CMAKE_MODULE_PATH to be able to include(module)
        {% if cmake_module_path %}
        list(PREPEND CMAKE_MODULE_PATH {{ cmake_module_path }})
        {% endif %}
        """)
        host_req = self._conanfile.dependencies.host
        build_req = self._conanfile.dependencies.direct_build
        test_req = self._conanfile.dependencies.test
        host_test_reqs = list(host_req.items()) + list(test_req.items())
        all_reqs = host_test_reqs + list(build_req.items())
        # gen_folder = self._conanfile.generators_folder.replace("\\", "/")
        # if not, test_cmake_add_subdirectory test fails
        # content.append('set(CMAKE_FIND_PACKAGE_PREFER_CONFIG ON)')
        pkg_paths = {}

        pkg_paths_multi = {}
        if os.path.exists(self._conan_cmakedeps_paths):
            existing_toolchain = load(self._conan_cmakedeps_paths)
            pattern_paths = r"list\(APPEND CONAN_([A-Za-z0-9-_]*)_DIR_MULTI \"([^)]*)\"\)"
            variable_match = re.findall(pattern_paths, existing_toolchain)
            for (captured_name, captured_path) in variable_match:
                path_list = pkg_paths_multi.setdefault(captured_name, [])
                if captured_path not in path_list:
                    path_list.append(captured_path)

        for req, dep in all_reqs:
            cmake_find_mode = self._cmakedeps.get_property("cmake_find_mode", dep)
            cmake_find_mode = cmake_find_mode or FIND_MODE_CONFIG
            cmake_find_mode = cmake_find_mode.lower()

            cmake_filename = self._cmakedeps.get_cmake_filename(dep)
            extra_variants = self._cmakedeps.get_property("cmake_file_name_variants", dep,
                                                          check_type=list) or []
            lowercase_variants = {variant.lower() for variant in extra_variants}
            if len(lowercase_variants) > 1:
                raise ConanException(f"'{dep.ref}' 'cmake_file_name_variants' property contains different words. "
                                     "They should be the same with different upper/lower cases only.")
            if lowercase_variants:
                if cmake_filename.lower() not in lowercase_variants:
                    is_cmake_filename_defined = self._cmakedeps.get_property("cmake_file_name", dep) is not None
                    if is_cmake_filename_defined:
                        extra_variants = []
                        msg = (f"'{dep.ref}' 'cmake_file_name_variants' property contains names "
                               f"with different casings than the defined name '{cmake_filename}'. "
                               f"The specified 'cmake_file_name'='{cmake_filename}' property "
                               f"will be used as the only name and the variants will be ignored.")
                        self._conanfile.output.warning(msg)
                    else:
                        msg = (f"'{dep.ref}' 'cmake_file_name_variants' property contains entries "
                               f"that differ from the default 'cmake_file_name'='{cmake_filename}'. "
                               f"They should be the same with different upper/lower cases only.")
                        raise ConanException(msg)
            pkg_names = set([cmake_filename] + extra_variants)
            # https://cmake.org/cmake/help/v3.22/guide/using-dependencies/index.html
            if cmake_find_mode == FIND_MODE_NONE:
                cps = glob.glob(os.path.join(dep.package_folder, f"**/{cmake_filename}.cps"),
                                recursive=True)
                if cps:
                    loc = os.path.dirname(os.path.join(dep.package_folder, cps[0]))
                    loc = loc.replace("\\", "/")
                    relative_path = relativize_path(loc, self._conanfile,
                                                    "${CMAKE_CURRENT_LIST_DIR}")
                    for pkg_name in pkg_names:
                        pkg_paths[pkg_name] = relative_path
                    continue

                try:
                    # This is irrespective of the components, it should be in the root cpp_info
                    # To define the location of the pkg-config.cmake file
                    build_dir = dep.cpp_info.builddirs[0]
                except IndexError:
                    build_dir = dep.package_folder
                pkg_folder = build_dir.replace("\\", "/") if build_dir else None
                if pkg_folder:
                    if any(os.path.isfile(os.path.join(pkg_folder, f + ext)) for f in pkg_names
                           for ext in ("-config.cmake", "Config.cmake")):
                        relative_path = relativize_path(pkg_folder, self._conanfile,
                                                        "${CMAKE_CURRENT_LIST_DIR}")
                        for pkg_name in pkg_names:
                            pkg_paths[pkg_name] = relative_path

                    for pkg_name in pkg_names:
                        existing_paths = pkg_paths_multi.setdefault(pkg_name, [])
                        if pkg_folder not in existing_paths:
                            existing_paths.append(pkg_folder)
                continue

            # If CMakeDeps generated, the folder is this one
            # content.append(f'set({pkg_name}_ROOT "{gen_folder}")')
            for pkg_name in pkg_names:
                pkg_paths[pkg_name] = "${CMAKE_CURRENT_LIST_DIR}"

        # CMAKE_PROGRAM_PATH | CMAKE_LIBRARY_PATH | CMAKE_INCLUDE_PATH
        cmake_program_path = self._get_cmake_paths([(req, dep) for req, dep in all_reqs if req.direct], "bindirs")
        cmake_library_path = self._get_cmake_paths(host_test_reqs, "libdirs")
        cmake_include_path = self._get_cmake_paths(host_test_reqs, "includedirs")
        cmake_framework_path = self._get_cmake_paths(host_test_reqs, "frameworkdirs")
        cmake_module_path = self._get_cmake_paths(all_reqs, "builddirs")
        context = {"host_runtime_dirs": self._get_host_runtime_dirs(),
                   "pkg_paths": pkg_paths,
                   "pkg_paths_multi": pkg_paths_multi,
                   "cmake_program_path": _join_paths(self._conanfile, cmake_program_path),
                   "cmake_library_path": _join_paths(self._conanfile, cmake_library_path),
                   "cmake_include_path": _join_paths(self._conanfile, cmake_include_path),
                   "cmake_framework_path": _join_paths(self._conanfile, cmake_framework_path),
                   "cmake_module_path": _join_paths(self._conanfile, cmake_module_path)
                   }
        content = Template(template, trim_blocks=True, lstrip_blocks=True).render(context)
        save(self._conanfile, self._conan_cmakedeps_paths, content)

    def _get_host_runtime_dirs(self):
        host_runtime_dirs = {}

        # Get the previous configuration
        if os.path.exists(self._conan_cmakedeps_paths):
            existing_toolchain = load(self._conan_cmakedeps_paths)
            pattern_lib_dirs = r"set\(CONAN_RUNTIME_LIB_DIRS ([^)]*)\)"
            variable_match = re.search(pattern_lib_dirs, existing_toolchain)
            if variable_match:
                capture = variable_match.group(1)
                matches = re.findall(r'"\$<\$<CONFIG:([A-Za-z]*)>:([^>]*)>"', capture)
                for config, paths in matches:
                    host_runtime_dirs.setdefault(config, []).append(paths)

        is_win = self._conanfile.settings.get_safe("os") == "Windows"

        host_req = self._conanfile.dependencies.host
        test_req = self._conanfile.dependencies.test
        for req in list(host_req.values()) + list(test_req.values()):
            config = req.settings.get_safe("build_type", self._cmakedeps.configuration)
            aggregated_cppinfo = req.cpp_info.aggregated_components()
            runtime_dirs = aggregated_cppinfo.bindirs if is_win else aggregated_cppinfo.libdirs
            for d in runtime_dirs:
                d = d.replace("\\", "/")
                d = relativize_path(d, self._conanfile, "${CMAKE_CURRENT_LIST_DIR}")
                existing = host_runtime_dirs.setdefault(config, [])
                if d not in existing:
                    existing.append(d)

        return ' '.join(f'"$<$<CONFIG:{c}>:{i}>"' for c, v in host_runtime_dirs.items() for i in v)
