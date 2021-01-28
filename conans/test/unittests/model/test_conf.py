import textwrap

import pytest

from conans.errors import ConanException
from conans.model.conf import ConfDefinition


@pytest.fixture()
def conf_definition():
    text = textwrap.dedent("""\
        tools.microsoft.msbuild:verbosity=minimal
        user.company.toolchain:flags=someflags""")
    c = ConfDefinition()
    c.loads(text)
    return c, text


def test_conf_definition(conf_definition):
    c, text = conf_definition
    # Round trip
    assert c.dumps() == text
    # access
    assert c["tools.microsoft.msbuild"].verbosity == "minimal"
    assert c["user.company.toolchain"].flags == "someflags"
    assert c["tools.microsoft.msbuild"].nonexist is None
    assert c["nonexist"].nonexist is None
    # bool
    assert bool(c)
    assert not bool(ConfDefinition())


def test_conf_update(conf_definition):
    c, _ = conf_definition
    text = textwrap.dedent("""\
       user.company.toolchain:flags=newvalue
       another.something:key=value""")
    c2 = ConfDefinition()
    c2.loads(text)
    c.update_conf_definition(c2)
    result = textwrap.dedent("""\
        another.something:key=value
        tools.microsoft.msbuild:verbosity=minimal
        user.company.toolchain:flags=newvalue""")
    assert c.dumps() == result


def test_conf_rebase(conf_definition):
    c, _ = conf_definition
    text = textwrap.dedent("""\
       user.company.toolchain:flags=newvalue
       another.something:key=value""")
    c2 = ConfDefinition()
    c2.loads(text)
    c.rebase_conf_definition(c2)
    # The c profile will have precedence, and "
    result = textwrap.dedent("""\
        tools.microsoft.msbuild:verbosity=minimal
        user.company.toolchain:flags=someflags""")
    assert c.dumps() == result


def test_conf_error_per_package():
    text = "*:core:verbosity=minimal"
    c = ConfDefinition()
    with pytest.raises(ConanException,
                       match=r"Conf '\*:core:verbosity=minimal' cannot have a package pattern"):
        c.loads(text)


def test_conf_error_uppercase():
    text = "tools.something:Verbosity=minimal"
    c = ConfDefinition()
    with pytest.raises(ConanException, match=r"Conf key 'Verbosity' must be lowercase"):
        c.loads(text)
    text = "tools.Something:verbosity=minimal"
    c = ConfDefinition()
    with pytest.raises(ConanException, match=r"Conf module 'tools.Something' must be lowercase"):
        c.loads(text)


def test_parse_spaces():
    text = "core:verbosity = minimal"
    c = ConfDefinition()
    c.loads(text)
    assert c["core"].verbosity == "minimal"
