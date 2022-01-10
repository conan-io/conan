import fnmatch
import os

from jinja2 import Template


from conans.cli.api.subapi import api_method
from conans.cli.conan_app import ConanApp
from conans.util.files import load
from conans import __version__


class NewAPI:

    _NOT_TEMPLATES = "not_templates"

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @api_method
    def get_builtin_template(self, template):
        from conans.cli.api.helpers.new.alias_new import alias_file
        from conans.cli.api.helpers.new.cmake_exe import cmake_exe_files
        from conans.cli.api.helpers.new.cmake_lib import cmake_lib_files
        new_templates = {"cmake_lib": cmake_lib_files,
                         "cmake_exe": cmake_exe_files,
                         "alias": alias_file}
        template_files = new_templates.get(template)
        return template_files

    @api_method
    def get_cache_template(self, template):
        app = ConanApp(self.conan_api.cache_folder)

        folder_template = None
        if os.path.isdir(template):
            folder_template = template
        else:
            folder = os.path.join(app.cache.cache_folder, "templates", "command/new", template)
            if os.path.exists(folder):
                folder_template = folder

        if folder_template is None:
            return None

        template_files, non_template_files = {}, {}
        excluded = os.path.join(folder_template, self._NOT_TEMPLATES)
        if os.path.exists(excluded):
            excluded = load(excluded)
            excluded = [] if not excluded else [s.strip() for s in excluded.splitlines() if
                                                s.strip()]
        else:
            excluded = []

        for d, _, fs in os.walk(folder_template):
            for f in fs:
                if f == self._NOT_TEMPLATES:
                    continue
                rel_d = os.path.relpath(d, folder_template) if d != folder_template else ""
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
        definitions["conan_version"] = __version__
        for k, v in template_files.items():
            k = Template(k, keep_trailing_newline=True).render(**definitions)
            v = Template(v, keep_trailing_newline=True).render(**definitions)
            if v:
                result[k] = v
        return result
