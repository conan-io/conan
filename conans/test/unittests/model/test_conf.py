import sys
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


@pytest.mark.parametrize("text, expected", [
    ("user.company.cpu:jobs=!", None),
    ("user.company.cpu:jobs=10", 10),
    ("user.company.build:ccflags=--m superflag", "--m superflag"),
    ("zlib:user.company.check:shared=True", True),
    ("zlib:user.company.check:shared_str='True'", '"True"'),
    ("user.company.list:objs=[1, 2, 3, 4, 'mystr', {'a': 1}]", [1, 2, 3, 4, 'mystr', {'a': 1}]),
    ("user.company.network:proxies={'url': 'http://api.site.com/api', 'dataType': 'json', 'method': 'GET'}",
     {'url': 'http://api.site.com/api', 'dataType': 'json', 'method': 'GET'})
])
def test_conf_get_different_type_input_objects(text, expected):
    """
    Testing any possible Python-evaluable-input-format introduced
    by the user
    """
    c = ConfDefinition()
    c.loads(text)
    assert c.get(text.split("=")[0]) == expected


def test_compose_conf_complex():
    """
    Testing the composition between several ConfDefiniton objects and with
    different value types
    """
    text = textwrap.dedent("""\
        user.company.cpu:jobs=10
        user.company.build:ccflags=--m superflag
        zlib:user.company.check:shared=True
        zlib:user.company.check:shared_str="True"
        user.company.list:objs=[1, 2, 3, 4, 'mystr', {'a': 1}]
        user.company.network:proxies={'url': 'http://api.site.com/api', 'dataType': 'json', 'method': 'GET'}
    """)
    c = ConfDefinition()
    c.loads(text)
    text = textwrap.dedent("""\
        user.company.cpu:jobs=5
        user.company.build:ccflags=--m otherflag
        zlib:user.company.check:shared=!
        zlib:user.company.check:shared_str="False"
        user.company.list:objs+=[5, 6]
        user.company.list:objs=+0
        user.company.network:proxies={'url': 'http://api.site.com/apiv2'}
        """)
    c2 = ConfDefinition()
    c2.loads(text)
    c.update_conf_definition(c2)
    expected_text = textwrap.dedent("""\
        user.company.cpu:jobs=5
        user.company.build:ccflags=--m otherflag
        user.company.list:objs=[0, 1, 2, 3, 4, 'mystr', {'a': 1}, 5, 6]
        user.company.network:proxies={'url': 'http://api.site.com/apiv2', 'dataType': 'json', 'method': 'GET'}
        zlib:user.company.check:shared=!
        zlib:user.company.check:shared_str="False"
    """)
    assert c.dumps() == expected_text


def test_conf_get_check_type_and_default():
    text = textwrap.dedent("""\
        user.company.cpu:jobs=5
        user.company.build:ccflags=--m otherflag
        user.company.list:objs=[0, 1, 2, 3, 4, 'mystr', {'a': 1}, 5, 6]
        user.company.network:proxies={'url': 'http://api.site.com/apiv2', 'dataType': 'json', 'method': 'GET'}
        zlib:user.company.check:shared=!
        zlib:user.company.check:shared_str="False"
    """)
    c = ConfDefinition()
    c.loads(text)
    assert c.get("user.company.cpu:jobs", check_type=int) == 5
    with pytest.raises(ConanException) as exc_info:
        c.get("user.company.cpu:jobs", check_type=list)
        assert "[conf] user.company.cpu:jobs must be a list-like object." in str(exc_info.value)
    # Check type does not affect to default value
    assert c.get("non:existing:conf", default=0, check_type=dict) == 0


def test_conf_pop():
    text = textwrap.dedent("""\
        user.company.cpu:jobs=5
        user.company.build:ccflags=--m otherflag
        user.company.list:objs=[0, 1, 2, 3, 4, 'mystr', {'a': 1}, 5, 6]
        user.company.network:proxies={'url': 'http://api.site.com/apiv2', 'dataType': 'json', 'method': 'GET'}
        zlib:user.company.check:shared=!
        zlib:user.company.check:shared_str="False"
    """)
    c = ConfDefinition()
    c.loads(text)

    assert c.pop("user.company.network:proxies") == {'url': 'http://api.site.com/apiv2', 'dataType': 'json', 'method': 'GET'}
    assert c.pop("tools.microsoft.msbuild:missing") is None
    assert c.pop("tools.microsoft.msbuild:missing", default="fake") == "fake"
    assert c.pop("zlib:user.company.check:shared_str") == '"False"'
