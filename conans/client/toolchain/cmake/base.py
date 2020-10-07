import os

from jinja2 import Template

from conans.util.files import save


class CMakeToolchainBase(object):
    filename = "conan_toolchain.cmake"
    project_include_filename = "conan_project_include.cmake"

    _template_project_include = None
    _template_toolchain = None

    def __init__(self, conanfile, *args, **kwargs):
        self._conanfile = conanfile

    def _get_template_context_data(self):
        """ Returns two dictionaries, the context for the '_template_toolchain' and
            the context for the '_template_project_include' templates.
        """
        return {}, {}

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
