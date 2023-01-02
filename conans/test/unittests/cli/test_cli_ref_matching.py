import pytest

from conan.internal.api.select_pattern import SelectPattern


@pytest.mark.parametrize("pattern, result",
                         [("*",                  ("*", "latest", None, "latest")),
                          ("zlib/1.2.11",        ("zlib/1.2.11", "latest", None, "latest")),
                          ("zlib/1.2.11#rev1",   ("zlib/1.2.11", "rev1", None, "latest")),
                          ("zlib/1.2.11:pid1",   ("zlib/1.2.11", "latest", "pid1", "latest"))])
def test_cli_pattern_matching(pattern, result):
    pattern = SelectPattern(pattern)
    assert result == (pattern.ref, pattern.rrev, pattern.package_id, pattern.prev)
