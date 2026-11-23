import pytest

from conan.errors import ConanException
from conan.api.model import RecipeReference
from conan.internal.model.recipe_ref import ref_matches


def test_recipe_reference():
    r = RecipeReference.loads("pkg/0.1")
    assert r.name == "pkg"
    assert r.version == "0.1"
    assert r.user is None
    assert r.channel is None
    assert r.revision is None
    assert str(r) == "pkg/0.1"
    assert repr(r) == "pkg/0.1"

    r = RecipeReference.loads("pkg/0.1@")
    assert r.name == "pkg"
    assert r.version == "0.1"
    assert r.user is None
    assert r.channel is None
    assert r.revision is None
    assert str(r) == "pkg/0.1"
    assert repr(r) == "pkg/0.1"

    r = RecipeReference.loads("pkg/0.1@user")
    assert r.name == "pkg"
    assert r.version == "0.1"
    assert r.user == "user"
    assert r.channel is None
    assert r.revision is None
    assert str(r) == "pkg/0.1@user"
    assert repr(r) == "pkg/0.1@user"


def test_recipe_reference_revisions():
    r = RecipeReference.loads("pkg/0.1#r1")
    assert r.name == "pkg"
    assert r.version == "0.1"
    assert r.user is None
    assert r.channel is None
    assert r.revision == "r1"
    assert str(r) == "pkg/0.1"
    assert repr(r) == "pkg/0.1#r1"

    r = RecipeReference.loads("pkg/0.1@user#r1")
    assert r.name == "pkg"
    assert r.version == "0.1"
    assert r.user == "user"
    assert r.channel is None
    assert r.revision == "r1"
    assert str(r) == "pkg/0.1@user"
    assert repr(r) == "pkg/0.1@user#r1"


def test_recipe_reference_timestamp():
    r = RecipeReference.loads("pkg/0.1#r1%123")
    assert r.name == "pkg"
    assert r.version == "0.1"
    assert r.user is None
    assert r.channel is None
    assert r.revision == "r1"
    assert str(r) == "pkg/0.1"
    assert repr(r) == "pkg/0.1#r1%123.0"
    # TODO: Improve the time format
    assert r.repr_humantime() == "pkg/0.1#r1 (1970-01-01 00:02:03 UTC)"

    r = RecipeReference.loads("pkg/0.1@user#r1%123")
    assert r.name == "pkg"
    assert r.version == "0.1"
    assert r.user == "user"
    assert r.channel is None
    assert r.revision == "r1"
    assert str(r) == "pkg/0.1@user"
    assert repr(r) == "pkg/0.1@user#r1%123.0"
    assert r.repr_humantime() == "pkg/0.1@user#r1 (1970-01-01 00:02:03 UTC)"


def test_recipe_reference_compare():
    r1 = RecipeReference.loads("pkg/1.3#1")
    r2 = RecipeReference.loads("pkg/1.22#2")
    assert r1 < r2
    assert sorted([r2, r1]) == [r1, r2]


def test_recipe_reference_dict_key_revision_lookup():
    """Using a RecipeReference as a dict key works when revisions are not defined
    """
    d = {RecipeReference.loads("pkg/0.1"): "v1",
         RecipeReference.loads("foo/0.1#rev1"): "v2"}

    assert d[RecipeReference.loads("pkg/0.1")] == "v1"
    assert d[RecipeReference.loads("pkg/0.1#rev2")] == "v1"
    assert d[RecipeReference.loads("foo/0.1")] == "v2"
    assert d[RecipeReference.loads("foo/0.1#rev1")] == "v2"
    assert d.get(RecipeReference.loads("foo/0.1#rev2")) is None


def test_error_pref():
    r1 = RecipeReference.loads("pkg/1.0#rrev1:pid#rrev2")
    with pytest.raises(ConanException) as exc:
        r1.validate_ref()
    assert "Invalid recipe reference 'pkg/1.0#rrev1:pid#rrev2' is a package reference" in str(exc)

    r1 = RecipeReference.loads("pkg/1.0:pid")
    with pytest.raises(ConanException) as exc:
        r1.validate_ref()
    assert "Invalid recipe reference 'pkg/1.0:pid' is a package reference" in str(exc)


@pytest.mark.parametrize("pattern, no_uc, user, user_channel, unnamed", [
    ("*", True, True, True, True),
    ("*/*", True, True, True, True),
    ("*@", True, False, False, False),
    ("!*@", False, True, True, True),
    ("~*@", False, True, True, True),
    ("*@myuser", False, True, False, False),
    ("*/*@myuser", False, True, False, False),
    ("*@myuser/*", False, False, True, False),
    ("*@*", False, True, True, False),
    ("!*@myuser", True, False, True, True),
])
def test_ref_matches_user_channel(pattern, no_uc, user, user_channel, unnamed):
    """ "@" patterns only select refs without user/channel. A ref with only user (valid in
    Conan 2) is not "without user/channel". An unnamed consumer is not selected by "@" patterns
    """
    for ref, expected in (("pkg/0.1", no_uc), ("pkg/0.1@myuser", user),
                          ("pkg/0.1@myuser/stable", user_channel), (None, unnamed)):
        ref = RecipeReference.loads(ref) if ref else None
        assert ref_matches(ref, pattern, is_consumer=bool(ref is None)) is expected, \
            f"{ref} {pattern}"


def test_ref_matches_consumer_pattern():
    """ "&" selects only the consumer, with "@" too, even if it is unnamed """
    unnamed = None
    for pattern in ("&", "&@"):
        assert ref_matches(unnamed, pattern, is_consumer=True)
        assert not ref_matches(RecipeReference.loads("pkg/0.1"), pattern, is_consumer=False)


@pytest.mark.parametrize("pattern, no_uc, user, user_channel, unnamed", [
    ("pkg/0.1@#rev1", True, False, False, False),
    ("*@#*", True, False, False, False),
    ("*/*@#rev1", True, False, False, False),
    ("!pkg/0.1@#rev1", False, True, True, True),
    ("pkg/0.1@myuser#rev1", False, True, False, False),
])
def test_ref_matches_no_user_channel_with_revision(pattern, no_uc, user, user_channel, unnamed):
    """ "pkg/0.1@#rev1" is a revision without user/channel, the unnamed consumer (without
    name, user, channel or revision) is not selected by it
    """
    for ref, expected in (("pkg/0.1#rev1", no_uc), ("pkg/0.1@myuser#rev1", user),
                          ("pkg/0.1@myuser/stable#rev1", user_channel), (None, unnamed)):
        ref = RecipeReference.loads(ref) if ref else None
        assert ref_matches(ref, pattern, is_consumer=bool(ref is None)) is expected, \
            f"{ref} {pattern}"
