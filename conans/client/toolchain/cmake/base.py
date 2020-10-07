import os
from collections import OrderedDict, defaultdict

from jinja2 import Template

from conans.client.build.cmake_flags import is_multi_configuration
from conans.errors import ConanException
from conans.util.files import save


class Variables(OrderedDict):
    _configuration_types = None  # Needed for py27 to avoid infinite recursion

    def __init__(self):
        super(Variables, self).__init__()
        self._configuration_types = {}

    def __getattribute__(self, config):
        try:
            return super(Variables, self).__getattribute__(config)
        except AttributeError:
            return self._configuration_types.setdefault(config, dict())

    @property
    def configuration_types(self):
        # Reverse index for the configuration_types variables
        ret = defaultdict(list)
        for conf, definitions in self._configuration_types.items():
            for k, v in definitions.items():
                ret[k].append((conf, v))
        return ret


class CMakeToolchainBase(object):
    filename = "conan_toolchain.cmake"
    project_include_filename = "conan_project_include.cmake"

    _template_project_include = None
    _template_toolchain = None

    def __init__(self, conanfile, **kwargs):
        self._conanfile = conanfile
        self.variables = Variables()
        self.preprocessor_definitions = Variables()

        # To find the generated cmake_find_package finders
        self.cmake_prefix_path = "${CMAKE_BINARY_DIR}"
        self.cmake_module_path = "${CMAKE_BINARY_DIR}"

        try:
            # This is only defined in the cache, not in the local flow
            self.install_prefix = self._conanfile.package_folder.replace("\\", "/")
        except AttributeError:
            # FIXME: In the local flow, we don't know the package_folder
            self.install_prefix = None

        try:
            self._build_shared_libs = "ON" if self._conanfile.options.shared else "OFF"
        except ConanException:
            self._build_shared_libs = None

        self.build_type = None

    def _get_template_context_data(self):
        """ Returns two dictionaries, the context for the '_template_toolchain' and
            the context for the '_template_project_include' templates.
        """
        tpl_toolchain_context = {
            "variables": self.variables,
            "variables_config": self.variables.configuration_types,
            "preprocessor_definitions": self.preprocessor_definitions,
            "preprocessor_definitions_config": self.preprocessor_definitions.configuration_types,
            "cmake_prefix_path": self.cmake_prefix_path,
            "cmake_module_path": self.cmake_module_path,
            "install_prefix": self.install_prefix,
            "shared_libs": self._build_shared_libs,
            "build_type": self.build_type,
        }
        return tpl_toolchain_context, {}

    def write_toolchain_files(self):
        tpl_toolchain_context, tpl_project_include_context = self._get_template_context_data()

        # Make it absolute, wrt to current folder, set by the caller
        conan_project_include_cmake = os.path.abspath(self.project_include_filename)
        conan_project_include_cmake = conan_project_include_cmake.replace("\\", "/")
        t = Template(self._template_project_include)
        content = t.render(**tpl_project_include_context)
        save(conan_project_include_cmake, content)

        t = Template(self._template_toolchain)
        content = t.render(conan_project_include_cmake=conan_project_include_cmake,
                           **tpl_toolchain_context)
        save(self.filename, content)
