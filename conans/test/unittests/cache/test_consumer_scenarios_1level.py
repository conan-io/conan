import os
import tempfile
import time

import pytest

from conan.cache.cache import Cache
from conan.cache.cache_implementation import CacheImplementation
from conan.locks.locks_manager import LocksManager
from conans.model.ref import ConanFileReference, PackageReference


@pytest.fixture(scope='module')
def populated_cache() -> Cache:
    with tempfile.TemporaryDirectory() as tmpdirname:
        locks_directory = os.path.join(tmpdirname, '.locks')
        locks_manager = LocksManager.create('fasteners', locks_directory=locks_directory)
        db_filename = os.path.join(tmpdirname, 'cache.sqlite3')
        cache = CacheImplementation.create('sqlite3', tmpdirname, locks_manager,
                                           filename=db_filename)

        # Now populate the cache
        for rrev in ('rrev1', 'rrev2', 'rrev3'):
            time.sleep(1)  # TODO: Add more resolution to timestamp in database
            for version in ('v1', 'v2', 'v3'):
                ref = ConanFileReference.loads(f'name/{version}#{rrev}')
                cache.get_or_create_reference_layout(ref)

                for pkg_id in ('pkg1', 'pkg2'):
                    for prev in ('prev1', 'prev2'):
                        pref = PackageReference.loads(f'{ref.full_str()}:{pkg_id}#{prev}')
                        cache.get_or_create_package_layout(pref)

        yield cache


def test_list_references(populated_cache):
    refs = list(populated_cache.list_references(only_latest_rrev=False))
    assert 9 == len(refs)

    refs = list(populated_cache.list_references(only_latest_rrev=True))
    assert 3 == len(refs)
    assert ['name/v1#rrev3', 'name/v2#rrev3', 'name/v3#rrev3'] == [r.full_str() for r in refs]


def test_search_references(populated_cache):
    refs = list(populated_cache.search_references('%name%', only_latest_rrev=False))
    assert 9 == len(refs)

    refs = list(populated_cache.search_references('%name%', only_latest_rrev=True))
    assert 3 == len(refs)
    assert ['name/v1#rrev3', 'name/v2#rrev3', 'name/v3#rrev3'] == [r.full_str() for r in refs]

    refs = list(populated_cache.search_references('%name/v1%', only_latest_rrev=False))
    assert 3 == len(refs)
    assert ['name/v1#rrev1', 'name/v1#rrev2', 'name/v1#rrev3'] == [r.full_str() for r in refs]

    refs = list(populated_cache.search_references('%name/v1%', only_latest_rrev=True))
    assert 1 == len(refs)
    assert ['name/v1#rrev3'] == [r.full_str() for r in refs]


def test_list_reference_versions(populated_cache):
    ref = ConanFileReference.loads('name/v1#notused')
    refs = list(populated_cache.list_reference_versions(ref, only_latest_rrev=False))
    assert 9 == len(refs)

    refs = list(populated_cache.list_reference_versions(ref, only_latest_rrev=True))
    assert 3 == len(refs)
    assert ['name/v1#rrev3', 'name/v2#rrev3', 'name/v3#rrev3'] == [r.full_str() for r in refs]
