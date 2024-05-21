from conan.api.conan_api import ConanAPI
from conans.model.recipe_ref import RecipeReference
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TurboTestClient


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
    api = ConanAPI(client.cache_folder)
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
