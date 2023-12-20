import pytest

from conans.errors import ConanException
from conans.model.recipe_ref import RecipeReference


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


def test_error_pref():
    r1 = RecipeReference.loads("pkg/1.0#rrev1:pid#rrev2")
    with pytest.raises(ConanException) as exc:
        r1.validate_ref()
    assert "Invalid recipe reference 'pkg/1.0#rrev1:pid#rrev2' is a package reference" in str(exc)

    r1 = RecipeReference.loads("pkg/1.0:pid")
    with pytest.raises(ConanException) as exc:
        r1.validate_ref()
    assert "Invalid recipe reference 'pkg/1.0:pid' is a package reference" in str(exc)
