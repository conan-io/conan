import pytest

from conans.cli.api.conan_api import ConanAPIV2
from conans.errors import ConanException
from conans.model.recipe_ref import RecipeReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TurboTestClient


def test_search_recipes():
    """
        Test the "api.search.recipes"
    """
    client = TurboTestClient(default_server_user=True)
    ref = RecipeReference.loads("foo/1.0")
    pref1 = client.create(ref, GenConanfile())
    conanfile_2 = GenConanfile().with_build_msg("change2")
    pref2 = client.create(ref, conanfile_2)
    pref3 = client.create(RecipeReference.loads("felipe/1.0"), conanfile_2)

    client.upload_all(pref1.ref, "default")
    client.upload_all(pref2.ref, "default")
    client.upload_all(pref3.ref, "default")

    # Search all the recipes locally and in the remote
    api = ConanAPIV2(client.cache_folder)
    for remote in [None, api.remotes.get("default")]:
        with client.mocked_servers():
            sot = api.search.recipes(query="f*", remote=remote)
            assert set(sot) == {RecipeReference.loads("foo/1.0"),
                                RecipeReference.loads("felipe/1.0")}

            sot = api.search.recipes(query="fo*", remote=remote)
            assert set(sot) == {RecipeReference.loads("foo/1.0")}

            sot = api.search.recipes(query=None, remote=remote)
            assert set(sot) == {RecipeReference.loads("foo/1.0"),
                                RecipeReference.loads("felipe/1.0")}

            sot = api.search.recipes(query="*i*", remote=remote)
            assert set(sot) == {RecipeReference.loads("felipe/1.0")}


@pytest.mark.parametrize("mode_remote", [False, True])
def test_resolve_recipe_revisions(mode_remote):
    """
    Test the "api.list.resolve_recipe_revisions"
    """
    client = TurboTestClient(default_server_user=True)
    ref = RecipeReference.loads("foo/1.0")
    pref1 = client.create(ref, GenConanfile().with_build_msg("change1"))
    pref2 = client.create(ref, GenConanfile().with_build_msg("change2"))
    pref3 = client.create(ref, GenConanfile().with_build_msg("change3"))
    ref2 = RecipeReference.loads("bar/1.0")
    pref2_1 = client.create(ref2, GenConanfile().with_build_msg("change1"))
    pref2_2 = client.create(ref2, GenConanfile().with_build_msg("change2"))
    pref2_3 = client.create(ref2, GenConanfile().with_build_msg("change3"))

    client.run("upload '*' -c --all -r default")

    api = ConanAPIV2(client.cache_folder)
    remote = api.remotes.get("default") if mode_remote else None

    with client.mocked_servers():
        sot = api.search.recipe_revisions("foo/1.0", remote)
        assert sot == [pref3.ref, pref2.ref, pref1.ref]

        sot = api.search.recipe_revisions("f*/1.0", remote)
        assert sot == [pref3.ref, pref2.ref, pref1.ref]

        sot = api.search.recipe_revisions("f*/*", remote)
        assert sot == [pref3.ref, pref2.ref, pref1.ref]

        sot = api.search.recipe_revisions("f*", remote)
        assert sot == [pref3.ref, pref2.ref, pref1.ref]

        sot = api.search.recipe_revisions("foo/1.0#*", remote)
        assert sot == [pref3.ref, pref2.ref, pref1.ref]

        sot = api.search.recipe_revisions("foo/1.0#{}*".format(pref2.ref.revision[:4]), remote)
        assert sot == [pref2.ref]

        sot = api.search.recipe_revisions("f*o/1*#{}*".format(pref2.ref.revision[:4]), remote)
        assert sot == [pref2.ref]

        sot = api.search.recipe_revisions("*f/1*#*", remote)
        assert sot == []

        sot = api.search.recipe_revisions("*", remote)
        assert sot == [pref2_3.ref, pref2_2.ref, pref2_1.ref, pref3.ref, pref2.ref, pref1.ref]

        assert pref2.ref.revision == pref2_2.ref.revision
        sot = api.search.recipe_revisions("*/*#{}".format(pref2.ref.revision), remote)
        assert sot == [pref2_2.ref, pref2.ref]

        assert pref2.ref.revision == pref2_2.ref.revision
        sot = api.search.recipe_revisions("*/1.0#{}".format(pref2.ref.revision), remote)
        assert sot == [pref2_2.ref, pref2.ref]

        sot = api.search.recipe_revisions(pref2.ref.repr_notime(), remote)
        assert sot == [pref2.ref]


@pytest.mark.parametrize("mode_remote", [False, True])
def test_resolve_package_revisions(mode_remote):
    """
    Test the "api.list.resolve_package_revisions"
    """
    client = TurboTestClient(default_server_user=True)

    def _create_packages(_ref):
        ret = []
        for i in range(2):
            for bt in "Debug", "Release":
                conanfile = GenConanfile().with_build_msg(str(i)).with_settings("build_type")
                ret.append(client.create(_ref, conanfile, "-s build_type={}".format(bt)))
        return ret

    prefs = _create_packages(RecipeReference.loads("foo/1.0"))
    prefs.extend(_create_packages(RecipeReference.loads("bar/2.0")))

    client.run("upload '*' -c --all -r default")

    api = ConanAPIV2(client.cache_folder)
    remote = api.remotes.get("default") if mode_remote else None

    with client.mocked_servers():
        with pytest.raises(ConanException) as e:
            api.search.package_revisions("*/1.0*:*", remote=remote)
        assert "Specify a recipe revision in the expression" in str(e.value)

        sot = api.search.package_revisions("*/*.0#*:*", remote=remote)
        assert set(sot) == set(prefs)

        sot = api.search.package_revisions("*/*.0#*:*#*", remote=remote)
        assert set(sot) == set(prefs)

        sot = api.search.package_revisions("foo/1.0#*:*", remote=remote)
        assert set(sot) == set([pref for pref in prefs if pref.ref.name == "foo"])

        sot = api.search.package_revisions("*/*.0#4*:*", remote=remote)
        assert set(sot) == set([pref for pref in prefs if pref.ref.revision.startswith("4")])

        sot = api.search.package_revisions("*/*.0#*:*#*1*", remote=remote)
        assert set(sot) == set([pref for pref in prefs if "1" in pref.revision])

        sot = api.search.package_revisions("*/*#*:*#*1*", remote=remote)
        assert set(sot) == set([pref for pref in prefs if "1" in pref.revision])

        sot = api.search.package_revisions("f*o/*#*:*#*", query="build_type=Debug", remote=remote)
        assert set(sot) == set([pref for pref in prefs
                                if pref.package_id == "040ce2bd0189e377b2d15eb7246a4274d1c63317" and
                                pref.ref.name == "foo"])

        sot = api.search.package_revisions("*/2.0#*:*#*", query="build_type=Debug", remote=remote)
        assert set(sot) == set([pref for pref in prefs
                                if pref.package_id == "040ce2bd0189e377b2d15eb7246a4274d1c63317" and
                                pref.ref.name == "bar"])

        sot = api.search.package_revisions(prefs[0].repr_notime(), remote=remote)
        assert sot == [prefs[0]]
