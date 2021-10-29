from conans.model.ref import RecipeReference


def test_recipe_reference():
    r = RecipeReference.loads("pkg/0.1")
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
    assert repr(r) == "pkg/0.1#r1%123"
    # TODO: Improve the time format
    assert r.format_time() == "pkg/0.1#r1(1970-01-01T00:02:03Z)"

    r = RecipeReference.loads("pkg/0.1@user#r1%123")
    assert r.name == "pkg"
    assert r.version == "0.1"
    assert r.user == "user"
    assert r.channel is None
    assert r.revision == "r1"
    assert str(r) == "pkg/0.1@user"
    assert repr(r) == "pkg/0.1@user#r1%123"
    assert r.format_time() == "pkg/0.1@user#r1(1970-01-01T00:02:03Z)"
