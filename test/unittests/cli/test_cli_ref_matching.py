import pytest

from conan.api.model import ListPattern
from conan.errors import ConanException


@pytest.mark.parametrize("pattern, result",
                         [("*",                  ("*", "latest", None, "latest")),
                          ("zlib/1.2.11",        ("zlib/1.2.11", "latest", None, "latest")),
                          ("zlib/1.2.11#rev1",   ("zlib/1.2.11", "rev1", None, "latest")),
                          ("zlib/1.2.11:pid1",   ("zlib/1.2.11", "latest", "pid1", "latest"))])
def test_cli_pattern_matching(pattern, result):
    pattern = ListPattern(pattern)
    assert result == (pattern.ref, pattern.rrev, pattern.package_id, pattern.prev)


def test_list_pattern():
    with pytest.raises(ConanException) as e:
        ListPattern("*:*", only_recipe=True)
    assert "Do not specify 'package_id' with 'only-recipe'" in str(e.value)


@pytest.mark.parametrize("pattern, search_ref", [
    # Pattern with user but no version: normalize to include /* so remote servers work correctly
    # (remote * doesn't cross / boundaries, so *@user* would fail to match name/ver@user*)
    ("potato",        "potato"),
    ("*@myuser*",        "*/*@myuser*"),
    ("*@myuser/chan*",   "*/*@myuser/chan*"),
    ("zlib@myuser",      "zlib/*@myuser"),
    # Patterns with explicit version are returned unchanged
    ("*/*@myuser*",      "*/*@myuser*"),
    ("zlib/*@myuser",    "zlib/*@myuser"),
    # Patterns without user are not affected
    ("*",                "*"),
    ("zlib/*",           "zlib/*"),
    ("*@",               "*@"),  # trailing @ means filter no-user, not a user pattern
])
def test_search_ref_normalization(pattern, search_ref):
    p = ListPattern(pattern)
    assert p.search_ref == search_ref
