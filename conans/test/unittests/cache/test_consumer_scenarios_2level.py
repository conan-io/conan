import os
import tempfile
import time

import pytest

from cache.cache_implementation_readonly import CacheImplementationReadOnly
from cache.cache_two_levels import CacheTwoLevels
from conan.cache.cache import Cache
from conan.cache.cache_implementation import CacheImplementation
from conan.locks.locks_manager import LocksManager
from conans.model.ref import ConanFileReference, PackageReference


def _add_packages_to_cache(cache: Cache, ref_name: str):
    for rrev in ('rrev1', 'rrev2', 'rrev3'):
        time.sleep(1)  # TODO: Add more resolution to timestamp in database
        for version in ('v1', 'v2', 'v3'):
            ref = ConanFileReference.loads(f'{ref_name}/{version}#{rrev}')
            cache.get_or_create_reference_layout(ref)

            for pkg_id in ('pkg1', 'pkg2'):
                for prev in ('prev1', 'prev2'):
                    pref = PackageReference.loads(f'{ref.full_str()}:{pkg_id}#{prev}')
                    cache.get_or_create_package_layout(pref)


@pytest.fixture(scope='module')
def populated_cache() -> Cache:
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
            _add_packages_to_cache(aux_user_cache, 'name')

            # Workspace cache
            db_ws_filename = os.path.join(wstmpdirname, 'cache.sqlite3')
            ws_cache = CacheImplementation.create('sqlite3', wstmpdirname, locks_manager,
                                                  filename=db_ws_filename)
            _add_packages_to_cache(aux_user_cache, 'other')
            # ... duplicate some 'name/v1' reference entries
            r1 = ws_cache.get_or_create_reference_layout(ConanFileReference.loads('name/v1#rrev1'))
            # TODO: Populate the ws-cache with packages

            cache = CacheTwoLevels(ws_cache, user_cache, locks_manager)
            yield cache

# TODO: Waiting for information about recipe-revision timestamps
