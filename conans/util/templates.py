# coding=utf-8

from jinja2 import Template


def render_layout_file(content, ref=None, settings=None, options=None):
    t = Template(content)
    return t.render(reference=ref, settings=settings, options=options)
