import pytest

from conan.internal.api.ref_pattern import RefPattern


@pytest.mark.parametrize("pattern, result",
                         [("*",                  ("*", None, None, None)),
                          ("zlib/1.2.11",        ("zlib/1.2.11", None, None, None)),
                          ("zlib/1.2.11#rev1",   ("zlib/1.2.11", "rev1", None, None)),
                          ("zlib/1.2.11:pid1",   ("zlib/1.2.11", None, "pid1", None))])
def test_cli_pattern_matching(pattern, result):
    pattern = RefPattern(pattern)
    assert result == (pattern.ref, pattern.rrev, pattern.package_id, pattern.prev)
