import pytest

from conans.model.recipe_ref import Version

v = [("1", "2"),
     ("1.0", "1.1"),
     ("1.1", "1.1.0"),  # generic 1.1 is earlier than 1.1.0
     ("1.0.2", "1.1.0"),
     ("1.3", "1.22"),
     ("1.1.3", "1.1.22"),
     ("1.1.1.3", "1.1.1.22"),
     ("1.1.1.1.3", "1.1.1.1.22"),
     # Different lengths
     ("1.0", "2"),
     ("1.2", "1.3.1"),
     ("1.0.2", "1.1"),
     # Now with letters
     ("1.1.a", "1.1.b"),
     ("1.1.1.abc", "1.1.1.abz"),
     ("a.b.c", "b.c"),
     # build is easy
     ("1.1+b1", "1.1+b2"),
     ("1.1+b.3", "1.1+b.22"),
     # pre-release is challenging
     ("1.1-pre1", "1.1-pre2"),
     ("1.1-alpha.3", "1.1-alpha.22"),
     ("1.1-alpha.3+b1", "1.1-alpha.3+b2"),
     ("1.1-alpha.1", "1.1"),
     ("1.1", "1.2-alpha1"),
     ("1.1-alpha.1", "1.1.0"),  # pre to the generic 1.1 is earlier than 1.1.0
     ]


@pytest.mark.parametrize("v1, v2", v)
def test_comparison(v1, v2):
    v1 = Version(v1)
    v2 = Version(v2)
    assert v1 < v2
    assert v2 > v1
    assert v1 != v2
    assert v1 <= v2
    assert v2 >= v1
