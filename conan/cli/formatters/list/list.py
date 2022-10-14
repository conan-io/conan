import os

from conan.api.output import cli_out_write
from conans.util.files import load
from conans import __version__ as client_version


def list_packages_html(info):
    ref, results, template_folder = info
    user_template = os.path.join(template_folder, "list_packages.html")
    template = load(user_template) if os.path.isfile(user_template) else list_packages_html
    content = template.render(reference=ref, results=results, base_template_path=template_folder,
                              version=client_version)
    cli_out_write(content)
