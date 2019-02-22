# coding=utf-8

from jinja2 import Template
from conans.errors import ConanException


def render_layout_file(content, ref=None, settings=None, options=None):
    t = Template(content)
    #settings = {k: v for k, v in settings.values_list} if settings else None
    #options = {k: v for k, v in options.values.as_list()} if options else None
    return t.render(reference=str(ref), settings=settings, options=options)
