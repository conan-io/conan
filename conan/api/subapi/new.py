import fnmatch
import os

from jinja2 import Template, StrictUndefined

from conan.api.subapi import api_method
from conans.util.files import load
from conans import __version__


class NewAPI:

    _NOT_TEMPLATES = "not_templates"  # Filename containing filenames of files not to be rendered

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @api_method
    def get_builtin_template(self, template_name):
        from conan.internal.api.new.alias_new import alias_file
        from conan.internal.api.new.cmake_exe import cmake_exe_files
        from conan.internal.api.new.cmake_lib import cmake_lib_files
        from conan.internal.api.new.meson_lib import meson_lib_files
        from conan.internal.api.new.meson_exe import meson_exe_files
        from conan.internal.api.new.msbuild_lib import msbuild_lib_files
        from conan.internal.api.new.msbuild_exe import msbuild_exe_files
        from conan.internal.api.new.bazel_lib import bazel_lib_files
        from conan.internal.api.new.bazel_exe import bazel_exe_files
        from conan.internal.api.new.autotools_lib import autotools_lib_files
        from conan.internal.api.new.autoools_exe import autotools_exe_files
        new_templates = {"cmake_lib": cmake_lib_files,
                         "cmake_exe": cmake_exe_files,
                         "meson_lib": meson_lib_files,
                         "meson_exe": meson_exe_files,
                         "msbuild_lib": msbuild_lib_files,
                         "msbuild_exe": msbuild_exe_files,
                         "bazel_lib": bazel_lib_files,
                         "bazel_exe": bazel_exe_files,
                         "autotools_lib": autotools_lib_files,
                         "autotools_exe": autotools_exe_files,
                         "alias": alias_file}
        template_files = new_templates.get(template_name)
        return template_files

    @api_method
    def get_template(self, template_folder):
        """ Load a template from a user absolute folder
        """
        if os.path.isdir(template_folder):
            return self._read_files(template_folder)

    @api_method
    def get_home_template(self, template_name):
        """ Load a template from the Conan home templates/command/new folder
        """
        folder_template = os.path.join(self.conan_api.home_folder, "templates", "command/new",
                                       template_name)
        if os.path.isdir(folder_template):
            return self._read_files(folder_template)

    def _read_files(self, template_folder):
        template_files, non_template_files = {}, {}
        excluded = os.path.join(template_folder, self._NOT_TEMPLATES)
        if os.path.exists(excluded):
            excluded = load(excluded)
            excluded = [] if not excluded else [s.strip() for s in excluded.splitlines() if
                                                s.strip()]
        else:
            excluded = []

        for d, _, fs in os.walk(template_folder):
            for f in fs:
                if f == self._NOT_TEMPLATES:
                    continue
                rel_d = os.path.relpath(d, template_folder) if d != template_folder else ""
                rel_f = os.path.join(rel_d, f)
                path = os.path.join(d, f)
                if not any(fnmatch.fnmatch(rel_f, exclude) for exclude in excluded):
                    template_files[rel_f] = load(path)
                else:
                    non_template_files[rel_f] = path

        return template_files, non_template_files

    @staticmethod
    def render(template_files, definitions):
        result = {}
        name = definitions.get("name", "Pkg")
        definitions["conan_version"] = __version__
        definitions["package_name"] = name.replace("-", "_").replace("+", "_").replace(".", "_")
        for k, v in template_files.items():
            k = Template(k, keep_trailing_newline=True, undefined=StrictUndefined).render(**definitions)
            v = Template(v, keep_trailing_newline=True, undefined=StrictUndefined).render(**definitions)
            if v:
                result[k] = v
        return result
