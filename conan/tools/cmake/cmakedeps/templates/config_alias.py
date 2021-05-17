import textwrap

from conan.tools.cmake.cmakedeps.templates import CMakeDepsFileTemplate
from conan.tools.cmake.cmakedeps.templates.config import ConfigTemplate

"""
For the alternative file-name:

FooConfig.cmake
foo-config.cmake

"""


class ConfigAliasTemplate(CMakeDepsFileTemplate):

    def __init__(self, req, configuration, alias_name):
        super(ConfigAliasTemplate, self).__init__(req, configuration)
        self.alias_name = alias_name

    @property
    def filename(self):
        if self.alias_name == self.alias_name.lower():
            return "{}-config.cmake".format(self.alias_name)
        else:
            return "{}Config.cmake".format(self.alias_name)

    @property
    def context(self):
        return {"name_original": ConfigTemplate(self.conanfile, configuration=None).filename}

    @property
    def template(self):
        return textwrap.dedent('include("${CMAKE_CURRENT_LIST_DIR}/{{ name_original }}")')
