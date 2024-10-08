import pytest

from conan.api.conan_api import ConanAPI
from conan.api.model import Remote
from conans.model.recipe_ref import RecipeReference
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


@pytest.mark.parametrize("remote_name", [None, "default"])
def test_search_recipes(remote_name):
    """
        Test the "api.search.recipes"
    """
    client = TestClient(default_server_user=True)
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . --name=foo --version=1.0")
    client.run("create . --name=felipe --version=2.0")
    client.save({"conanfile.py": GenConanfile().with_build_msg("change")})
    # Different version&revision, but 1.0 < 2.0, which has an earlier timestamp
    client.run("create . --name=felipe --version=1.0")
    # Different revision, newer timestamp
    client.run("create . --name=foo --version=1.0")

    client.run("upload * -r=default -c")

    # Search all the recipes locally and in the remote
    api = ConanAPI(client.cache_folder)
    remote = api.remotes.get(remote_name) if remote_name else None

    with client.mocked_servers():
        sot = api.search.recipes(query="f*", remote=remote)
        assert sot == [RecipeReference.loads("felipe/1.0"),
                       RecipeReference.loads("felipe/2.0"),
                       RecipeReference.loads("foo/1.0")]

        sot = api.search.recipes(query="fo*", remote=remote)
        assert sot == [RecipeReference.loads("foo/1.0")]

        sot = api.search.recipes(query=None, remote=remote)
        assert sot == [RecipeReference.loads("felipe/1.0"),
                       RecipeReference.loads("felipe/2.0"),
                       RecipeReference.loads("foo/1.0")]

        sot = api.search.recipes(query="*i*", remote=remote)
        assert sot == [RecipeReference.loads("felipe/1.0"),
                       RecipeReference.loads("felipe/2.0")]
