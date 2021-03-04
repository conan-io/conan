import pytest

from conan.cache.cache_two_levels import CacheTwoLevels
from conan.cache.package_layout import PackageLayout
from conan.cache.cache import Cache
from conan.cache.recipe_layout import RecipeLayout
from conans.model.ref import ConanFileReference, PackageReference


def dump(cache: Cache):
    from io import StringIO
    output = StringIO()
    output.write('\n')
    cache.dump(output)
    print(output.getvalue())


def is_ws_cache(folder: str):
    # FIXME: This is conditioned to the value assigned in the fixtures
    return '-ws-cache' in folder


def is_user_cache(folder: str):
    # FIXME: This is conditioned to the value assigned in the fixtures
    return '-user-cache' in folder


@pytest.fixture
def populated_cache(cache_2level: CacheTwoLevels) -> Cache:
    # Populate cache with some initial data
    cache_2level._user_cache.get_reference_layout(ConanFileReference.loads('name/v1@user/channel#1'))

    cache_2level._workspace.get_reference_layout(ConanFileReference.loads('other/v1#1'))
    cache_2level._user_cache.get_reference_layout(ConanFileReference.loads('other/v1#1'))
    yield cache_2level


def test_export(populated_cache: Cache):
    # Unknown reference is retrieved from the workspace cache
    ref = ConanFileReference.loads('name/version@user/channel')
    unknown_ref_layout: RecipeLayout = populated_cache.get_reference_layout(ref)
    assert is_ws_cache(str(unknown_ref_layout.export()))
    assert not is_user_cache(str(unknown_ref_layout.export()))

    # Known reference is retrieved from the user cache
    ref = ConanFileReference.loads('name/v1@user/channel#1')
    known_ref_layout: RecipeLayout = populated_cache.get_reference_layout(ref)
    assert not is_ws_cache(str(known_ref_layout.export()))
    assert is_user_cache(str(known_ref_layout.export()))

    dump(populated_cache)
    # Known reference, if present in both caches, it will be retrieve from the workspace one
    ref = ConanFileReference.loads('other/v1#1')
    dupe_layout: RecipeLayout = populated_cache.get_reference_layout(ref)
    assert is_ws_cache(str(dupe_layout.export()))
    assert not is_user_cache(str(dupe_layout.export()))


def test_create_package_for_new_reference(populated_cache: Cache):
    # Create package for a new reference (reference is created in the workspace cache)
    ref = ConanFileReference.loads('ref/version')
    ref_layout: RecipeLayout = populated_cache.get_reference_layout(ref)
    assert is_ws_cache(str(ref_layout.export()))

    # Once we know the revision, we can ask for a package layout (to the cache itself)
    ref = ref.copy_with_rev('rrev1')
    ref_layout.assign_rrev(ref, False)
    pref = PackageReference.loads(f'{ref.full_str()}:123456798')
    pkg_layout: PackageLayout = populated_cache.get_package_layout(pref)
    assert is_ws_cache(str(pkg_layout.package()))
    assert is_ws_cache(str(pkg_layout.build()))

    # ... or using the reference layout we already have
    pkg_layout: PackageLayout = ref_layout.get_package_layout(pref)
    assert is_ws_cache(str(pkg_layout.package()))
    assert is_ws_cache(str(pkg_layout.build()))


def test_create_package_for_existing_reference_in_workspace_cache(populated_cache: Cache):
    ref = ConanFileReference.loads('other/v1#1')

    # Once we know the revision, we can ask for a package layout (to the cache itself)
    pref = PackageReference.loads(f'{ref.full_str()}:123456798')
    pkg_layout: PackageLayout = populated_cache.get_package_layout(pref)
    assert is_ws_cache(str(pkg_layout.package()))
    assert is_ws_cache(str(pkg_layout.build()))

    # ... or using the reference layout we already have
    ref_layout: RecipeLayout = populated_cache.get_reference_layout(ref)
    assert is_ws_cache(str(ref_layout.export()))

    pkg_layout: PackageLayout = ref_layout.get_package_layout(pref)
    assert is_ws_cache(str(pkg_layout.package()))
    assert is_ws_cache(str(pkg_layout.build()))


def test_create_package_for_existing_reference_in_user_cache(populated_cache: Cache):
    ref = ConanFileReference.loads('name/v1@user/channel#1')
    ref_layout: RecipeLayout = populated_cache.get_reference_layout(ref)
    assert is_user_cache(str(ref_layout.export()))

    # Once we know the revision, we can ask for a package layout (to the cache itself)
    pref = PackageReference.loads(f'{ref.full_str()}:123456798')
    pkg_layout: PackageLayout = populated_cache.get_package_layout(pref)
    assert is_ws_cache(str(pkg_layout.package()))
    assert is_ws_cache(str(pkg_layout.build()))

    # ... or using the reference layout we already have
    #ref_layout: RecipeLayout = populated_cache.get_reference_layout(ref)
    #assert is_user_cache(str(ref_layout.export()))

    #pkg_layout: PackageLayout = ref_layout.get_package_layout(pref)
    #assert is_ws_cache(str(pkg_layout.package()))
    #assert is_ws_cache(str(pkg_layout.build()))
