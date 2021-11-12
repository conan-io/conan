import copy

import pytest

from conans.cli.api.conan_api import ConanAPIV2
from conans.model.recipe_ref import RecipeReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TurboTestClient


def _pref_gen():
    """
    With the same recipe, every time the package is built the package revision will be different
    """
    package_lines = 'save(self, os.path.join(self.package_folder, "foo.txt"), str(time.time()))'
    gen = GenConanfile().with_package(package_lines).with_import("import os, time") \
        .with_import("from conan.tools.files import save")
    return gen


def test_get_latests_revisions_api():
    """
        Test the "api.references.latest_package" and "api.references.latest_recipe"
    """
    client = TurboTestClient(default_server_user=True)
    ref = RecipeReference.loads("foo/1.0")
    pref1 = client.create(ref, _pref_gen().with_build_msg("change1"))
    conanfile_2 = _pref_gen().with_build_msg("change2")
    pref2 = client.create(ref, conanfile_2)
    # Will generate a different package revision
    pref2b = client.create(ref, conanfile_2)

    client.upload_all(pref1.ref, "default")
    client.upload_all(pref2.ref, "default")

    # Check latest recipe revision
    api = ConanAPIV2(client.cache_folder)
    sot = api.references.latest_recipe(ref)
    assert pref2.ref == pref2b.ref
    assert sot == pref2.ref

    # Check latest package revision in cache
    pref = copy.copy(pref2b)
    pref.revision = None
    sot = api.references.latest_package(pref)
    assert sot == pref2b
    assert pref2b != pref2

    # Check in remote
    with client.mocked_servers():
        sot = api.references.latest_recipe(ref, api.remotes.get("default"))
        assert sot == pref2.ref

    with client.mocked_servers():
        sot = api.references.latest_package(pref, api.remotes.get("default"))
        assert sot == pref2b

    # Check error if passed a reference with revision
    with pytest.raises(AssertionError):
        api.references.latest_recipe(pref1.ref)

    with pytest.raises(AssertionError):
        api.references.latest_package(pref1)


def test_get_recipe_revisions():
    """
    Test the "api.references.recipe_revisions"
    """
    client = TurboTestClient(default_server_user=True)
    ref = RecipeReference.loads("foo/1.0")
    pref1 = client.create(ref, GenConanfile().with_build_msg("change1"))
    pref2 = client.create(ref, GenConanfile().with_build_msg("change2"))
    pref3 = client.create(ref, GenConanfile().with_build_msg("change3"))
    client.upload_all(pref1.ref, "default")
    client.upload_all(pref2.ref, "default")
    client.upload_all(pref3.ref, "default")

    api = ConanAPIV2(client.cache_folder)

    # Check the revisions locally
    sot = api.references.recipe_revisions(ref)
    assert sot == [pref3.ref, pref2.ref, pref1.ref]

    # Check the revisions in the remote
    with client.mocked_servers():
        sot = api.references.recipe_revisions(ref, api.remotes.get("default"))
        assert sot == [pref3.ref, pref2.ref, pref1.ref]


def test_get_package_revisions():
    """
    Test the "api.references.package_revisions"
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

    api = ConanAPIV2(client.cache_folder)

    # Check the revisions locally
    sot = api.references.package_revisions(_pref)
    assert sot == [pref3, pref2, pref1]

    # Check the revisions in the remote
    with client.mocked_servers():
        sot = api.references.package_revisions(_pref, api.remotes.get("default"))
        assert sot == [pref3, pref2, pref1]
