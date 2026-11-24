import gc

import pytest
from jinja2 import StrictUndefined, UndefinedError
from jinja2.runtime import Macro

from conan.internal.util.templates import compiled_template


def test_compiled_template_options():
    """ The options are part of the cache key, the same text with other options is another
    compiled template """
    text = "  {% if a %}\nx\n  {% endif %}\n{{ a }}\n"
    template = compiled_template(text)
    assert compiled_template(text) is template
    assert template.render(a=1) == "x\n1"
    assert template.render() == ""

    no_trim = compiled_template(text, trim_blocks=False, lstrip_blocks=False)
    assert no_trim is not template
    assert no_trim.render(a=1) == "  \nx\n  \n1"

    assert compiled_template(text, keep_trailing_newline=True).render(a=1) == "x\n1\n"

    with pytest.raises(UndefinedError):
        compiled_template(text, undefined=StrictUndefined).render()



def test_compiled_template_macros_no_reference_cycles():
    """ The macros that call other macros reference the render context, and the context them, the
    rendered templates clear the context, so they don't leave cycles with the GC disabled """
    template = compiled_template("{% macro b(x) %}{{ x }}{% endmacro %}"
                                 "{% macro a(x) %}{{ b(x) }}{% endmacro %}{{ a(v) }}")
    enabled = gc.isenabled()
    gc.collect()
    gc.disable()
    gc.set_debug(gc.DEBUG_SAVEALL)
    try:
        assert template.render(v=1) == "1"
        assert template.render({"v": 2}) == "2"
        gc.collect()
        assert not any(isinstance(o, Macro) for o in gc.garbage)
    finally:
        gc.set_debug(0)
        gc.garbage.clear()
        if enabled:
            gc.enable()
