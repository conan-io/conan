import textwrap

import pytest

from conans.model.conf import ConfDefinition


@pytest.fixture()
def conf_definition():
    text = textwrap.dedent("""\
        tools.microsoft.MSBuild:verbosity=minimal
        user.company.Toolchain:flags=someflags""")
    c = ConfDefinition()
    c.loads(text)
    return c, text


def test_conf_definition(conf_definition):
    c, text = conf_definition
    # Round trip
    assert c.dumps() == text
    # access
    assert c["tools.microsoft.MSBuild"].verbosity == "minimal"
    assert c["user.company.Toolchain"].flags == "someflags"
    assert c["tools.microsoft.MSBuild"].nonexist is None
    assert c["nonexist"].nonexist is None
    # bool
    assert bool(c)
    assert not bool(ConfDefinition())


def test_conf_update(conf_definition):
    c, _ = conf_definition
    text = textwrap.dedent("""\
       user.company.Toolchain:flags=newvalue
       another.something:key=value""")
    c2 = ConfDefinition()
    c2.loads(text)
    c.update_conf_definition(c2)
    result = textwrap.dedent("""\
        another.something:key=value
        tools.microsoft.MSBuild:verbosity=minimal
        user.company.Toolchain:flags=newvalue""")
    assert c.dumps() == result


def test_conf_rebase(conf_definition):
    c, _ = conf_definition
    text = textwrap.dedent("""\
       user.company.Toolchain:flags=newvalue
       another.something:key=value""")
    c2 = ConfDefinition()
    c2.loads(text)
    c.rebase_conf_definition(c2)
    # The c profile will have precedence, and "
    result = textwrap.dedent("""\
        tools.microsoft.MSBuild:verbosity=minimal
        user.company.Toolchain:flags=someflags""")
    assert c.dumps() == result


