import pytest

from conans.model.version import Version

v = [("1.2.3",
      (1, 2, 3), None, None),
     ("1.2.3",
      ('1', '2', '3'), None, None),
     ("master+build2",
      'master', None, "build2"),
     ("1.2.3-alpha1+build2",
      (1, 2, 3), "alpha1", "build2"),
     ("1.2.3+build2",
      (1, 2, 3), None, "build2"),
     ("1.2.3b.4-pre.1.2b+build.1.1b",
      (1, 2, "3b", 4), "pre.1.2b", "build.1.1b"),
     ("0.2.3+b178",
      (0, 2, 3), None, "b178"),
     ("1.2.3.4.5",
      (1, 2, 3, 4, 5), None, None),
     (9,
      9, None, None),
     (1.2,
      (1, 2), None, None),
     ("",
      '', None, None),
     ("+build2",
      '', None, "build2"),
     ("1.2.3-pre.4-5-6+build.7-8-9",
      "1.2.3", "pre.4-5-6", "build.7-8-9"),
     ("1-", "1", "", None)
     ]


@pytest.mark.parametrize("v_str, main, pre, build", v)
def test_parse(v_str, main, pre, build):
    v1 = Version(v_str)
    assert v1.main == main if type(main) is tuple else tuple([main])
    assert v1.pre == pre
    assert v1.build == build
    assert str(v1) == str(v_str)
