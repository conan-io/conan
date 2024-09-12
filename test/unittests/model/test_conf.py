import textwrap

import pytest

from conans.errors import ConanException
from conans.model.conf import ConfDefinition


@pytest.fixture()
def conf_definition():
    text = textwrap.dedent("""\
        tools.build:verbosity=quiet
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
    assert c.get("tools.build:verbosity") == "quiet"
    assert c.get("user.company.toolchain:flags") == "someflags"
    assert c.get("user.microsoft.msbuild:nonexist") is None
    assert c.get("user:nonexist") is None
    # bool
    assert bool(c)
    assert not bool(ConfDefinition())


@pytest.mark.parametrize("conf_name", [
    "tools.doesnotexist:never",
    "tools:doesnotexist",
    "core.doesnotexist:never",
    "core:doesnotexist"
])
def test_conf_definition_error(conf_definition, conf_name):
    c, text = conf_definition
    with pytest.raises(ConanException):
        c.get(conf_name)


def test_conf_update(conf_definition):
    c, _ = conf_definition
    text = textwrap.dedent("""\
        user.company.toolchain:flags=newvalue
        user.something:key=value
    """)
    c2 = ConfDefinition()
    c2.loads(text)
    c.update_conf_definition(c2)
    result = textwrap.dedent("""\
        tools.build:verbosity=quiet
        user.company.toolchain:flags=newvalue
        user.something:key=value
    """)
    assert c.dumps() == result


def test_conf_rebase(conf_definition):
    c, _ = conf_definition
    text = textwrap.dedent("""\
       user.company.toolchain:flags=newvalue
       tools.build:verbosity=verbose""")
    c2 = ConfDefinition()
    c2.loads(text)
    c.rebase_conf_definition(c2)
    # The c profile will have precedence, and "
    result = textwrap.dedent("""\
        tools.build:verbosity=quiet
        user.company.toolchain:flags=someflags
    """)
    assert c.dumps() == result


def test_conf_error_per_package():
    text = "*:core:non_interactive=minimal"
    c = ConfDefinition()
    with pytest.raises(ConanException,
                       match=r"Conf '\*:core:non_interactive' cannot have a package pattern"):
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
    text = "core:non_interactive = minimal"
    c = ConfDefinition()
    c.loads(text)
    assert c.get("core:non_interactive") == "minimal"


@pytest.mark.parametrize("text, expected", [
    ("user.company.cpu:jobs=!", None),
    ("user.company.cpu:jobs=10", 10),
    ("user.company.build:ccflags=--m superflag", "--m superflag"),
    ("zlib:user.company.check:shared=True", True),
    ("zlib:user.company.check:shared_str='True'", "'True'"),
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


@pytest.mark.parametrize("text1, text2, expected", [
    ("user.company.list:objs=[2, 3]", "user.company.list:objs=+[0, 1]", [0, 1, 2, 3]),
    ("user.company.list:objs=[2, 3]", "user.company.list:objs+=[4, 5]", [2, 3, 4, 5]),
    ("user.company.list:objs=[2, 3]", "user.company.list:objs+={'a': 1}", [2, 3, {'a': 1}]),
    ("user.company.list:objs=[2, 3]", "user.company.list:objs=+start", ["start", 2, 3]),
    ("user.company.list:objs=[2, 3]", "user.company.list:objs=[0, 1]", [0, 1]),
])
def test_conf_list_operations(text1, text2, expected):
    c1 = ConfDefinition()
    c1.loads(text1)
    c2 = ConfDefinition()
    c2.loads(text2)
    c1.update_conf_definition(c2)
    assert c1.get(text1.split("=")[0]) == expected


@pytest.mark.parametrize("text1, text2", [
    ("user.company.list:objs=value", "user.company.list:objs=['value']"),
    ("user.company.list:objs='value'", "user.company.list:objs=+[0, 1]"),
    ("user.company.list:objs={'a': 1}", "user.company.list:objs+={'b': 1}"),
    ("user.company.list:objs=True", "user.company.list:objs+=False"),
    ("user.company.list:objs=10", "user.company.list:objs=+11")
])
def test_conf_list_operations_fails_with_wrong_types(text1, text2):
    c1 = ConfDefinition()
    c1.loads(text1)
    c1_value_type = type(c1.get("user.company.list:objs")).__name__
    c2 = ConfDefinition()
    c2.loads(text2)
    with pytest.raises(ConanException) as exc_info:
        c1.update_conf_definition(c2)
    assert "It's not possible to compose list values and %s ones" % c1_value_type \
           in str(exc_info.value)


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
        user.company.list:objs+={'b': 2}
        user.company.network:proxies={'url': 'http://api.site.com/apiv2'}
        """)
    c2 = ConfDefinition()
    c2.loads(text)
    c.update_conf_definition(c2)
    expected_text = textwrap.dedent("""\
        user.company.build:ccflags=--m otherflag
        user.company.cpu:jobs=5
        user.company.list:objs=[0, 1, 2, 3, 4, 'mystr', {'a': 1}, 5, 6, {'b': 2}]
        user.company.network:proxies={'url': 'http://api.site.com/apiv2'}
        zlib:user.company.check:shared=!
        zlib:user.company.check:shared_str="False"
    """)

    assert c.dumps() == expected_text


def test_compose_conf_dict_updates():
    c = ConfDefinition()
    c.loads("user.company:mydict={'1': 'a'}\n"
            "user.company:mydict2={'1': 'a'}")
    c2 = ConfDefinition()
    c2.loads("user.company:mydict={'2': 'b'}\n"
             "user.company:mydict2*={'2': 'b'}")
    c.update_conf_definition(c2)
    assert c.dumps() == ("user.company:mydict={'2': 'b'}\n"
                         "user.company:mydict2={'1': 'a', '2': 'b'}\n")


def test_conf_get_check_type_and_default():
    text = textwrap.dedent("""\
        user.company.cpu:jobs=5
        user.company.build:ccflags=--m otherflag
        user.company.list:objs=[0, 1, 2, 3, 4, 'mystr', {'a': 1}, 5, 6]
        user.company.network:proxies={'url': 'http://api.site.com/apiv2', 'dataType': 'json', 'method': 'GET'}
        zlib:user.company.check:shared=!
        zlib:user.company.check:shared_str="False"
        zlib:user.company.check:static_str=off
        user.company.list:newnames+=myname
        core.download:parallel=True
    """)
    c = ConfDefinition()
    c.loads(text)
    assert c.get("user.company.cpu:jobs", check_type=int) == 5
    assert c.get("user.company.cpu:jobs", check_type=str) == "5"  # smart conversion
    with pytest.raises(ConanException) as exc_info:
        c.get("user.company.cpu:jobs", check_type=list)
        assert "[conf] user.company.cpu:jobs must be a list-like object." in str(exc_info.value)
    # Check type does not affect to default value
    assert c.get("user.non:existing", default=0, check_type=dict) == 0
    assert c.get("zlib:user.company.check:shared") is None  # unset value
    assert c.get("zlib:user.company.check:shared", default=[]) == []  # returning default
    assert c.get("zlib:user.company.check:shared", default=[], check_type=list) == []  # not raising exception
    assert c.get("zlib:user.company.check:shared_str") == '"False"'
    assert c.get("zlib:user.company.check:shared_str", check_type=bool) is False  # smart conversion
    assert c.get("zlib:user.company.check:static_str") == "off"
    assert c.get("zlib:user.company.check:static_str", check_type=bool) is False  # smart conversion
    assert c.get("user.company.list:newnames") == ["myname"]  # Placeholder is removed
    with pytest.raises(ConanException) as exc_info:
        c.get("core.download:parallel", check_type=int)
    assert ("[conf] core.download:parallel must be a int-like object. "
            "The value 'True' introduced is a bool object") in str(exc_info.value)


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
    assert c.pop("user.microsoft.msbuild:missing") is None
    assert c.pop("user.microsoft.msbuild:missing", default="fake") == "fake"
    assert c.pop("zlib:user.company.check:shared_str") == '"False"'


def test_conf_choices():
    confs = textwrap.dedent("""
    user.category:option1=1
    user.category:option2=3""")
    c = ConfDefinition()
    c.loads(confs)
    assert c.get("user.category:option1", choices=[1, 2]) == 1
    with pytest.raises(ConanException):
        c.get("user.category:option2", choices=[1, 2])


def test_conf_choices_default():
    # Does not conflict with the default value
    confs = textwrap.dedent("""
        user.category:option1=1""")
    c = ConfDefinition()
    c.loads(confs)
    assert c.get("user.category:option1", choices=[1, 2], default=7) == 1
    assert c.get("user.category:option2", choices=[1, 2], default=7) == 7


@pytest.mark.parametrize("scope", ["", "pkg/1.0:"])
@pytest.mark.parametrize("conf", [
    "user.foo:bar=1",
    "user:bar=1"
])
def test_conf_scope_patterns_ok(scope, conf):
    final_conf = scope + conf
    c = ConfDefinition()
    c.loads(final_conf)
    # Check it doesn't raise
    c.validate()


@pytest.mark.parametrize("conf", ["user.foo.bar=1"])
@pytest.mark.parametrize("scope, assert_message", [
    ("", "Either 'user.foo.bar' does not exist in configuration list"),
    ("pkg/1.0:", "Either 'pkg/1.0:user.foo.bar' does not exist in configuration list"),
])
def test_conf_scope_patterns_bad(scope, conf, assert_message):
    final_conf = scope + conf
    c = ConfDefinition()
    with pytest.raises(ConanException) as exc_info:
        c.loads(final_conf)
        c.validate()
    assert assert_message in str(exc_info.value)
