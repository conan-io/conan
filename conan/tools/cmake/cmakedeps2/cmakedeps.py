import os
import re
import textwrap

from jinja2 import Template

from conan.internal import check_duplicated_generator
from conan.tools.cmake.cmakedeps2.config import ConfigTemplate2
from conan.tools.cmake.cmakedeps2.config_version import ConfigVersionTemplate2
from conan.tools.cmake.cmakedeps2.target_configuration import TargetConfigurationTemplate2
from conan.tools.cmake.cmakedeps2.targets import TargetsTemplate2
from conan.tools.files import save
from conan.errors import ConanException
from conans.model.dependencies import get_transitive_requires
from conans.util.files import load

FIND_MODE_MODULE = "module"
FIND_MODE_CONFIG = "config"
FIND_MODE_NONE = "none"
FIND_MODE_BOTH = "both"


class CMakeDeps2:

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self.configuration = str(self._conanfile.settings.build_type)

        # These are just for legacy compatibility, but not use at al
        self.build_context_activated = []
        self.build_context_build_modules = []
        self.build_context_suffix = {}
        # Enable/Disable checking if a component target exists or not
        self.check_components_exist = False

        self._properties = {}

    def generate(self):
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
        for require, dep in list(host_req.items()) + list(build_req.items()) + list(test_req.items()):
            cmake_find_mode = self.get_property("cmake_find_mode", dep)
            cmake_find_mode = cmake_find_mode or FIND_MODE_CONFIG
            cmake_find_mode = cmake_find_mode.lower()
            if cmake_find_mode == FIND_MODE_NONE:
                continue

            config = ConfigTemplate2(self, dep)
            ret[config.filename] = config.content()
            config_version = ConfigVersionTemplate2(self, dep)
            ret[config_version.filename] = config_version.content()

            targets = TargetsTemplate2(self, dep)
            ret[targets.filename] = targets.content()
            target_configuration = TargetConfigurationTemplate2(self, dep, require)
            ret[target_configuration.filename] = target_configuration.content()
        return ret

    def set_property(self, dep, prop, value, build_context=False):
        """
        Using this method you can overwrite the :ref:`property<CMakeDeps Properties>` values set by
        the Conan recipes from the consumer.

        :param dep: Name of the dependency to set the :ref:`property<CMakeDeps Properties>`. For
         components use the syntax: ``dep_name::component_name``.
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
            return dep.cpp_info.get_property(prop, check_type=check_type) if not comp_name \
                else dep.cpp_info.components[comp_name].get_property(prop, check_type=check_type)

    def get_cmake_filename(self, dep, module_mode=None):
        """Get the name of the file for the find_package(XXX)"""
        # This is used by CMakeDeps to determine:
        # - The filename to generate (XXX-config.cmake or FindXXX.cmake)
        # - The name of the defined XXX_DIR variables
        # - The name of transitive dependencies for calls to find_dependency
        if module_mode and self._get_find_mode(dep) in [FIND_MODE_MODULE, FIND_MODE_BOTH]:
            ret = self.get_property("cmake_module_file_name", dep)
            if ret:
                return ret
        ret = self.get_property("cmake_file_name", dep)
        return ret or dep.ref.name

    def _get_find_mode(self, dep):
        """
        :param dep: requirement
        :return: "none" or "config" or "module" or "both" or "config" when not set
        """
        tmp = self.get_property("cmake_find_mode", dep)
        if tmp is None:
            return "config"
        return tmp.lower()

    def get_transitive_requires(self, conanfile):
        # Prepared to filter transitive tool-requires with visible=True
        return get_transitive_requires(self._conanfile, conanfile)


class _PathGenerator:
    _conan_cmakedeps_paths = "conan_cmakedeps_paths.cmake"

    def __init__(self, cmakedeps, conanfile):
        self._conanfile = conanfile
        self._cmakedeps = cmakedeps

    def generate(self):
        template = textwrap.dedent("""\
            {% for pkg_name, folder in pkg_paths.items() %}
            set({{pkg_name}}_DIR "{{folder}}")
            {% endfor %}
            {% if host_runtime_dirs %}
            set(CONAN_RUNTIME_LIB_DIRS {{ host_runtime_dirs }} )
            {% endif %}
            """)

        host_req = self._conanfile.dependencies.host
        build_req = self._conanfile.dependencies.direct_build
        test_req = self._conanfile.dependencies.test

        # gen_folder = self._conanfile.generators_folder.replace("\\", "/")
        # if not, test_cmake_add_subdirectory test fails
        # content.append('set(CMAKE_FIND_PACKAGE_PREFER_CONFIG ON)')
        pkg_paths = {}
        for req, dep in list(host_req.items()) + list(build_req.items()) + list(test_req.items()):
            cmake_find_mode = self._cmakedeps.get_property("cmake_find_mode", dep)
            cmake_find_mode = cmake_find_mode or FIND_MODE_CONFIG
            cmake_find_mode = cmake_find_mode.lower()

            pkg_name = self._cmakedeps.get_cmake_filename(dep)
            # https://cmake.org/cmake/help/v3.22/guide/using-dependencies/index.html
            if cmake_find_mode == FIND_MODE_NONE:
                try:
                    build_dir = dep.cpp_info.builddirs[0]
                except IndexError:
                    build_dir = dep.package_folder
                pkg_folder = build_dir.replace("\\", "/") if build_dir else None
                if pkg_folder:
                    config_file = ConfigTemplate2(self, dep).filename
                    if os.path.isfile(os.path.join(pkg_folder, config_file)):

                        pkg_paths[pkg_name] = pkg_folder
                continue

            # If CMakeDeps generated, the folder is this one
            # content.append(f'set({pkg_name}_ROOT "{gen_folder}")')
            pkg_paths[pkg_name] = "${CMAKE_CURRENT_LIST_DIR}"

        context = {"host_runtime_dirs": self._get_host_runtime_dirs(),
                   "pkg_paths": pkg_paths}
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
        for req in self._conanfile.dependencies.host.values():
            config = req.settings.get_safe("build_type", self._cmakedeps.configuration)
            cppinfo = req.cpp_info.aggregated_components()
            runtime_dirs = cppinfo.bindirs if is_win else cppinfo.libdirs
            for d in runtime_dirs:
                d = d.replace("\\", "/")
                existing = host_runtime_dirs.setdefault(config, [])
                if d not in existing:
                    existing.append(d)

        return ' '.join(f'"$<$<CONFIG:{c}>:{i}>"' for c, v in host_runtime_dirs.items() for i in v)
