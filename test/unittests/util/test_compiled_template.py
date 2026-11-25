import pytest
from jinja2 import StrictUndefined, UndefinedError

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

