import json
import os

from jinja2 import Template, select_autoescape

from conan.api.output import cli_out_write
from conan.cli.formatters.list.search_table_html import list_packages_html_template
from conans.util.files import load
from conans import __version__ as client_version


def list_packages_html(result):
    results = result["results"]
    cli_args = result["cli_args"]
    conan_api = result["conan_api"]
    template_folder = os.path.join(conan_api.cache_folder, "templates")
    user_template = os.path.join(template_folder, "list_packages.html")
    template = load(user_template) if os.path.isfile(user_template) else list_packages_html_template
    template = Template(template, autoescape=select_autoescape(['html', 'xml']))
    content = template.render(results=json.dumps(results), base_template_path=template_folder,
                              version=client_version, cli_args=cli_args)
    cli_out_write(content)
