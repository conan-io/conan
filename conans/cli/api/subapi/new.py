import fnmatch
import os

from jinja2 import Template

from conans.cli.api.helpers.new import new_templates
from conans.cli.api.subapi import api_method
from conans.cli.conan_app import ConanApp
from conans.errors import ConanException
from conans.util.files import load
from conans import __version__


class NewAPI:

    _NOT_TEMPLATES = "not_templates"

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @api_method
    def new(self, template, definitions):
        app = ConanApp(self.conan_api.cache_folder)

        # Find the template
        template_files = None
        if os.path.isdir(template):
            template_files = self._get_files(template)
        else:
            folder_template = os.path.join(app.cache.cache_folder, "templates", "command/new",
                                           template)
            if os.path.exists(folder_template):
                template_files = self._get_files(folder_template)

        # If not in cache or user, then check if it is a predefined one
        if template_files is None:
            template_files = new_templates.get(template)

        if not template_files:
            raise ConanException("Template doesn't exist or not a folder: {}".format(template))

        excluded = template_files.get(self._NOT_TEMPLATES)
        excluded = [] if not excluded else [s.strip() for s in excluded.splitlines() if s.strip()]

        result = {}
        definitions["conan_version"] = __version__
        for k, v in template_files.items():
            if not any(fnmatch.fnmatch(k, exclude) for exclude in excluded):
                k = self._render_template(k, definitions)
                v = self._render_template(v, definitions)
            if v:
                result[k] = v
        return result

    def _get_files(self, folder):
        files = {}
        excluded = os.path.join(folder, self._NOT_TEMPLATES)
        if os.path.exists(excluded):
            excluded = load(excluded)
            excluded = [] if not excluded else [s.strip() for s in excluded.splitlines() if
                                                s.strip()]
        else:
            excluded = []
        for d, _, fs in os.walk(folder):
            for f in fs:
                rel_d = os.path.relpath(d, folder) if d != folder else ""
                rel_f = os.path.join(rel_d, f)
                path = os.path.join(d, f)
                if not any(fnmatch.fnmatch(rel_f, exclude) for exclude in excluded):
                    files[rel_f] = load(path)  # text, encodings
                else:
                    files[rel_f] = open(path, "rb").read() # binaries
        return files

    @staticmethod
    def _render_template(text, defines):
        t = Template(text, keep_trailing_newline=True)
        return t.render(**defines)
