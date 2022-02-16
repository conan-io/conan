import textwrap

import pytest

from conans.errors import ConanException
from conans.model.conf import ConfDefinition


@pytest.fixture()
def conf_definition():
    text = textwrap.dedent("""\
        tools.microsoft.msbuild:verbosity=minimal
        user.company.toolchain:flags=someflags
    """)
    c = ConfDefinition()
    c.loads(text)
    return c, text


def test_conf_definition(conf_definition):
    c, text = conf_definition
    # Round trip
    assert c.dumps() == text
    # access
    assert c["tools.microsoft.msbuild:verbosity"] == "minimal"
    assert c["user.company.toolchain:flags"] == "someflags"
    assert c["tools.microsoft.msbuild:nonexist"] is None
    assert c["nonexist:nonexist"] is None
    # bool
    assert bool(c)
    assert not bool(ConfDefinition())


def test_conf_update(conf_definition):
    c, _ = conf_definition
    text = textwrap.dedent("""\
        user.company.toolchain:flags=newvalue
        another.something:key=value
    """)
    c2 = ConfDefinition()
    c2.loads(text)
    c.update_conf_definition(c2)
    result = textwrap.dedent("""\
        tools.microsoft.msbuild:verbosity=minimal
        user.company.toolchain:flags=newvalue
        another.something:key=value
    """)
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
        user.company.toolchain:flags=someflags
    """)
    assert c.dumps() == result


def test_conf_error_per_package():
    text = "*:core:verbosity=minimal"
    c = ConfDefinition()
    with pytest.raises(ConanException,
                       match=r"Conf '\*:core:verbosity' cannot have a package pattern"):
        c.loads(text)


def test_conf_error_uppercase():
    text = "tools.something:Verbosity=minimal"
    c = ConfDefinition()
    with pytest.raises(ConanException, match=r"Conf 'tools.something:Verbosity' must be lowercase"):
        c.loads(text)
    text = "tools.Something:verbosity=minimal"
    c = ConfDefinition()
    with pytest.raises(ConanException,
                       match=r"Conf 'tools.Something:verbosity' must be lowercase"):
        c.loads(text)


def test_parse_spaces():
    text = "core:verbosity = minimal"
    c = ConfDefinition()
    c.loads(text)
    assert c["core:verbosity"] == "minimal"


def test_conf_other_patterns_and_access():
    text = textwrap.dedent("""\
        tools.microsoft.msbuild:verbosity=minimal
        tools.cmake.cmaketoolchain:generator=CMake
        user.company.toolchain:flags=["oneflag", "secondflag"]
        openssl:user.company.toolchain:flags=["myflag"]
        zlib:user.company.toolchain:flags=["zflag"]
    """)
    c = ConfDefinition()
    c.loads(text)
    text = textwrap.dedent("""\
        tools.microsoft.msbuild:verbosity=Quiet
        user.company.toolchain:flags=+["zeroflag"]
        user.company.toolchain:flags+=thirdflag
        openssl:user.company.toolchain:flags=!
        tools.cmake.cmaketoolchain:generator=!
        zlib:user.company.toolchain:flags=+z2flag
        """)
    c2 = ConfDefinition()
    c2.loads(text)
    c.update_conf_definition(c2)
    expected = textwrap.dedent("""\
        tools.microsoft.msbuild:verbosity=Quiet
        user.company.toolchain:flags=zeroflag
        user.company.toolchain:flags+=oneflag
        user.company.toolchain:flags+=secondflag
        user.company.toolchain:flags+=thirdflag
        tools.cmake.cmaketoolchain:generator=!
        openssl:user.company.toolchain:flags=!
        zlib:user.company.toolchain:flags=z2flag
        zlib:user.company.toolchain:flags+=zflag
    """)
    assert c.dumps() == expected
    assert c["tools.microsoft.msbuild:verbosity"] == "Quiet"  # unset == ""
    assert c["user.company.toolchain:flags"] == ["zeroflag", "oneflag", "secondflag", "thirdflag"]
    assert c["openssl:user.company.toolchain:flags"] is None
    assert c["tools.cmake.cmaketoolchain:generator"] is None


def test_conf_get(conf_definition):
    c, _ = conf_definition
    text = textwrap.dedent("""\
        tools.microsoft.msbuild:verbosity=+another
        tools.microsoft.msbuild:verbosity=!
        user.company.toolchain:flags=oneflag
        user.company.toolchain:flags+=secondflag
        zlib:user.company.toolchain:flags=z1flag
        zlib:user.company.toolchain:flags+=z2flag
        openssl:user.company.toolchain:flags=oflag""")
    c2 = ConfDefinition()
    c2.loads(text)
    c.update_conf_definition(c2)
    assert c.get("tools.microsoft.msbuild:verbosity") == ""  # unset == ""
    assert c.get("tools.microsoft.msbuild:verbosity") == []
    assert c.get("tools.microsoft.msbuild:missing", default="fake") == "fake"
    assert c.get("user.company.toolchain:flags") == "oneflag secondflag"
    assert c.get("zlib:user.company.toolchain:flags") == "z1flag z2flag"
    assert c.get("openssl:user.company.toolchain:flags") == "oflag"
    assert c.get("openssl:user.company.toolchain:flags") == ["oflag"]


def test_conf_pop(conf_definition):
    c, _ = conf_definition
    assert c.pop("tools.microsoft.msbuild:missing") is None
    assert c.pop("tools.microsoft.msbuild:missing", default="fake") == "fake"
    assert c.pop("tools.microsoft.msbuild:verbosity") == "minimal"
    assert c.pop("tools.microsoft.msbuild:verbosity") is None
    assert c.pop("user.company.toolchain:flags") == "someflags"
