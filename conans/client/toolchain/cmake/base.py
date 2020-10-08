import os
from collections import OrderedDict, defaultdict

from jinja2 import Template

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

    def __init__(self, conanfile, *args, **kwargs):
        self._conanfile = conanfile
        self.variables = Variables()
        self.preprocessor_definitions = Variables()
        try:
            # This is only defined in the cache, not in the local flow
            self.install_prefix = self._conanfile.package_folder.replace("\\", "/")
        except AttributeError:
            # FIXME: In the local flow, we don't know the package_folder
            self.install_prefix = None

    def _get_template_context_data(self):
        """ Returns two dictionaries, the context for the '_template_toolchain' and
            the context for the '_template_project_include' templates.
        """
        ctxt_toolchain = {
            "variables": self.variables,
            "variables_config": self.variables.configuration_types,
            "preprocessor_definitions": self.preprocessor_definitions,
            "preprocessor_definitions_config": self.preprocessor_definitions.configuration_types,
            "install_prefix": self.install_prefix,
        }
        return ctxt_toolchain, {}

    def write_toolchain_files(self):
        ctxt_toolchain, ctxt_project_include = self._get_template_context_data()

        # Make it absolute, wrt to current folder, set by the caller
        conan_project_include_cmake = os.path.abspath(self.project_include_filename)
        conan_project_include_cmake = conan_project_include_cmake.replace("\\", "/")
        t = Template(self._template_project_include)
        content = t.render(**ctxt_project_include)
        save(conan_project_include_cmake, content)

        t = Template(self._template_toolchain)
        content = t.render(conan_project_include_cmake=conan_project_include_cmake, **ctxt_toolchain)
        save(self.filename, content)
