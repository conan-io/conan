"""
Gather all the utilities related to Jinja2 templates.
"""

import os

from jinja2 import Environment, FileSystemLoader, ChoiceLoader, select_autoescape, Template

from conans.assets.templates import dict_loader


def get_template(template_name, templates_folder):
    # Loader order: first current working dir, then 'templates' folder, fallback to dictionary
    loader = ChoiceLoader([
        FileSystemLoader(os.getcwd()),
        FileSystemLoader(templates_folder),
        dict_loader
    ])

    env = Environment(loader=loader, autoescape=select_autoescape(['html', 'xml']))
    return env.get_template(template_name)


def render_layout_file(content, ref=None, settings=None, options=None):
    t = Template(content)
    return t.render(reference=ref, settings=settings, options=options)
