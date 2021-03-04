import os
import tempfile

import pytest

from conan.cache.cache import Cache
from conan.cache.cache_implementation import CacheImplementation
from conan.cache.cache_implementation_readonly import CacheImplementationReadOnly
from conan.cache.cache_two_levels import CacheTwoLevels
from conan.cache.exceptions import ReadOnlyCache
from conan.cache.package_layout import PackageLayout
from conan.cache.recipe_layout import RecipeLayout
from conans.model.ref import ConanFileReference, PackageReference
from conans.util import files
from locks.locks_manager import LocksManager


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
def populated_cache() -> Cache:
    # Retrieve a 2-level cache based on sqlite3 and fasteners, with some packages in it

    # Some references to populate the cache with
    cmake_ref = ConanFileReference.loads('cmake/version#1')
    zlib_ref = ConanFileReference.loads('zlib/version#1')
    library_ref = ConanFileReference.loads('library/version#1')

    def create_ref_layout(cache, ref):
        layout, _ = cache.get_or_create_reference_layout(ref)
        files.save(os.path.join(str(layout.export()), 'conanfile.py'),
                   f"# Reference '{ref.full_str}'")

    with tempfile.TemporaryDirectory(suffix='-ws-cache') as wstmpdirname:
        with tempfile.TemporaryDirectory(suffix='-user-cache') as usertmpdirname:
            locks_directory = os.path.join(usertmpdirname, '.locks')
            locks_manager = LocksManager.create('fasteners', locks_directory=locks_directory)

            # User level cache (read-only)
            db_user_filename = os.path.join(usertmpdirname, 'cache.sqlite3')
            user_cache = CacheImplementationReadOnly.create('sqlite3', usertmpdirname, locks_manager,
                                                            filename=db_user_filename)

            # ...we cannot populate a read-only cache, we need to use auxiliary one
            aux_user_cache = CacheImplementation.create('sqlite3', usertmpdirname, locks_manager,
                                                        filename=db_user_filename)
            create_ref_layout(aux_user_cache, cmake_ref)
            create_ref_layout(aux_user_cache, zlib_ref)

            # Workspace cache
            db_ws_filename = os.path.join(wstmpdirname, 'cache.sqlite3')
            ws_cache = CacheImplementation.create('sqlite3', wstmpdirname, locks_manager,
                                                  filename=db_ws_filename)
            create_ref_layout(ws_cache, zlib_ref)
            create_ref_layout(ws_cache, library_ref)

            cache = CacheTwoLevels(ws_cache, user_cache, locks_manager)
            yield cache


def test_export(populated_cache: Cache):
    # Unknown reference is retrieved from the workspace cache
    ref = ConanFileReference.loads('name/version@user/channel')
    unknown_ref_layout, created = populated_cache.get_or_create_reference_layout(ref)
    assert created
    assert is_ws_cache(str(unknown_ref_layout.export()))
    assert not is_user_cache(str(unknown_ref_layout.export()))

    # Known reference is retrieved from the user cache
    ref = ConanFileReference.loads('cmake/version#1')
    known_ref_layout: RecipeLayout = populated_cache.get_reference_layout(ref)
    assert not is_ws_cache(str(known_ref_layout.export()))
    assert is_user_cache(str(known_ref_layout.export()))

    # Known reference, if present in both caches, it will be retrieve from the workspace one
    ref = ConanFileReference.loads('zlib/version#1')
    dupe_layout: RecipeLayout = populated_cache.get_reference_layout(ref)
    assert is_ws_cache(str(dupe_layout.export()))
    assert not is_user_cache(str(dupe_layout.export()))


def test_create_package_for_new_reference(populated_cache: Cache):
    # Create package for a new reference (reference is created in the workspace cache)
    ref = ConanFileReference.loads('ref/version')
    ref_layout, created = populated_cache.get_or_create_reference_layout(ref)
    assert created
    assert is_ws_cache(str(ref_layout.export()))

    # Once we know the revision, we can ask for a package layout (to the cache itself)
    ref = ref.copy_with_rev('rrev1')
    ref_layout.assign_rrev(ref, False)
    pref = PackageReference.loads(f'{ref.full_str()}:1111111')
    pkg_layout, created = populated_cache.get_or_create_package_layout(pref)
    assert True
    assert is_ws_cache(str(pkg_layout.package()))
    assert is_ws_cache(str(pkg_layout.build()))

    # ... or using the reference layout we already have
    pref2 = PackageReference.loads(f'{ref.full_str()}:2222222')
    pkg_layout2: PackageLayout = ref_layout.get_package_layout(pref2)
    assert is_ws_cache(str(pkg_layout2.package()))
    assert is_ws_cache(str(pkg_layout2.build()))


def test_create_package_for_existing_reference_in_workspace_cache(populated_cache: Cache):
    ref = ConanFileReference.loads('library/version#1')

    # Once we know the revision, we can ask for a package layout (to the cache itself)
    pref = PackageReference.loads(f'{ref.full_str()}:11111')
    pkg_layout, created = populated_cache.get_or_create_package_layout(pref)
    assert created
    assert is_ws_cache(str(pkg_layout.package()))
    assert is_ws_cache(str(pkg_layout.build()))

    # ... or using the reference layout we already have
    ref_layout: RecipeLayout = populated_cache.get_reference_layout(ref)
    assert is_ws_cache(str(ref_layout.export()))

    pref2 = PackageReference.loads(f'{ref.full_str()}:222222')
    pkg_layout2: PackageLayout = ref_layout.get_package_layout(pref2)
    assert is_ws_cache(str(pkg_layout2.package()))
    assert is_ws_cache(str(pkg_layout2.build()))


def test_create_package_for_existing_reference_in_user_cache(populated_cache: Cache):
    ref = ConanFileReference.loads('cmake/version#1')
    ref_layout: RecipeLayout = populated_cache.get_reference_layout(ref)
    assert is_user_cache(str(ref_layout.export()))

    # Once we know the revision, we can ask for a package layout (to the cache itself)
    pref = PackageReference.loads(f'{ref.full_str()}:1111111')
    pkg_layout, created = populated_cache.get_or_create_package_layout(pref)
    assert created
    assert is_ws_cache(str(pkg_layout.package()))
    assert is_ws_cache(str(pkg_layout.build()))

    # Now the reference is also in the workspace cache too
    ref_layout: RecipeLayout = populated_cache.get_reference_layout(ref)
    assert is_ws_cache(str(ref_layout.export()))


def test_create_package_for_existing_reference_in_user_cache_via_layout(populated_cache: Cache):
    ref = ConanFileReference.loads('cmake/version#1')
    ref_layout: RecipeLayout = populated_cache.get_reference_layout(ref)
    assert is_user_cache(str(ref_layout.export()))

    # Check that the user cannot use a workaround to create packages in the user cache
    pref = PackageReference.loads(f'{ref.full_str()}:1111111')
    with pytest.raises(ReadOnlyCache) as excinfo:
        ref_layout.get_package_layout(pref)
    assert "Cannot create packages using a read-only recipe layout" == str(excinfo.value)
