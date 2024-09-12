import copy


from conan.api.conan_api import ConanAPI
from conans.model.recipe_ref import RecipeReference
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TurboTestClient, TestClient


def _pref_gen():
    """
    With the same recipe, every time the package is built the package revision will be different
    """
    package_lines = 'save(self, os.path.join(self.package_folder, "foo.txt"), str(time.time()))'
    gen = GenConanfile().with_package(package_lines).with_import("import os, time") \
        .with_import("from conan.tools.files import save")
    return gen


def test_get_recipe_revisions():
    """
    Test the "api.list.recipe_revisions"
    """
    client = TurboTestClient(default_server_user=True)
    ref = RecipeReference.loads("foo/1.0")
    pref1 = client.create(ref, GenConanfile().with_build_msg("change1"))
    pref2 = client.create(ref, GenConanfile().with_build_msg("change2"))
    pref3 = client.create(ref, GenConanfile().with_build_msg("change3"))
    client.upload_all(pref1.ref, "default")
    client.upload_all(pref2.ref, "default")
    client.upload_all(pref3.ref, "default")

    api = ConanAPI(client.cache_folder)

    # Check the revisions locally
    sot = api.list.recipe_revisions(ref)
    assert sot == [pref3.ref, pref2.ref, pref1.ref]

    # Check the revisions in the remote
    with client.mocked_servers():
        sot = api.list.recipe_revisions(ref, api.remotes.get("default"))
        assert sot == [pref3.ref, pref2.ref, pref1.ref]


def test_get_package_revisions():
    """
    Test the "api.list.package_revisions"
    """
    client = TurboTestClient(default_server_user=True)
    ref = RecipeReference.loads("foo/1.0")
    gen = _pref_gen()
    # FIXME: The upload only takes the latest package revision, so do the upload after creating it
    pref1 = client.create(ref, gen)
    client.upload_all(pref1.ref, "default")
    pref2 = client.create(ref, gen)
    client.upload_all(pref1.ref, "default")
    pref3 = client.create(ref, gen)
    client.upload_all(pref1.ref, "default")

    _pref = copy.copy(pref1)
    _pref.revision = None

    api = ConanAPI(client.cache_folder)

    # Check the revisions locally
    sot = api.list.package_revisions(_pref)
    assert sot == [pref3, pref2, pref1]

    # Check the revisions in the remote
    with client.mocked_servers():
        sot = api.list.package_revisions(_pref, api.remotes.get("default"))
        assert sot == [pref3, pref2, pref1]


def test_search_recipes_no_user_channel_only():
    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . --name foo --version 1.0 --user user --channel channel")
    client.run("create . --name foo --version 1.0")
    client.run("list foo/1.0@")
    assert "foo/1.0@user/channel" not in client.out
    assert "foo/1.0" in client.out
