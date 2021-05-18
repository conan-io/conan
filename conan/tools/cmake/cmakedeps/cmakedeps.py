import os

from conan.tools.cmake.cmakedeps.templates.config import ConfigTemplate
from conan.tools.cmake.cmakedeps.templates.config_version import ConfigVersionTemplate
from conan.tools.cmake.cmakedeps.templates.macros import MacrosTemplate
from conan.tools.cmake.cmakedeps.templates.target_configuration import TargetConfigurationTemplate
from conan.tools.cmake.cmakedeps.templates.target_data import ConfigDataTemplate
from conan.tools.cmake.cmakedeps.templates.targets import TargetsTemplate
from conans.util.files import save


class CMakeDeps(object):

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self.arch = self._conanfile.settings.get_safe("arch")
        self.configuration = str(self._conanfile.settings.build_type)
        self.configurations = [v for v in conanfile.settings.build_type.values_range if v != "None"]

    def generate(self):
        # Current directory is the generators_folder
        generator_files = self.content
        for generator_file, content in generator_files.items():
            save(generator_file, content)

    @property
    def content(self):
        macros = MacrosTemplate()
        ret = {macros.filename: macros.render()}

        host_requires = {r.ref.name: r for r in
                         self._conanfile.dependencies.transitive_host_requires}
        # Iterate all the transitive requires
        for req in host_requires.values():

            config_version = ConfigVersionTemplate(req, self.configuration)
            ret[config_version.filename] = config_version.render()

            data_target = ConfigDataTemplate(req, self.configuration, self.arch)
            ret[data_target.filename] = data_target.render()

            target_configuration = TargetConfigurationTemplate(req, self.configuration)
            ret[target_configuration.filename] = target_configuration.render()

            targets = TargetsTemplate(req)
            ret[targets.filename] = targets.render()

            config = ConfigTemplate(req, self.configuration)
            # Check if the XXConfig.cmake exists to keep the first generated configuration
            # to only include the build_modules from the first conan install. The rest of the
            # file is common for the different configurations.
            if not os.path.exists(config.filename):
                ret[config.filename] = config.render()
        return ret
