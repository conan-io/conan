import os
import tempfile

import pytest

from conan.cache.cache_two_levels import CacheTwoLevels
from conan.cache.cache import Cache
from conan.cache.cache_implementation import CacheImplementation
from conan.locks.locks_manager import LocksManager


@pytest.fixture
def cache_memory() -> CacheImplementation:
    locks_manager = LocksManager.create('memory')
    with tempfile.TemporaryDirectory() as tmpdirname:
        cache = CacheImplementation.create('memory', tmpdirname, locks_manager)
        yield cache


@pytest.fixture
def cache_sqlite3() -> CacheImplementation:
    with tempfile.TemporaryDirectory() as tmpdirname:
        db_filename = os.path.join(tmpdirname, 'locks.sqlite3')
        locks_manager = LocksManager.create('sqlite3', filename=db_filename)
        cache = CacheImplementation.create('sqlite3', tmpdirname, locks_manager,
                                           filename=db_filename)
        yield cache


@pytest.fixture
def cache_sqlite3_fasteners() -> CacheImplementation:
    with tempfile.TemporaryDirectory() as tmpdirname:
        locks_directory = os.path.join(tmpdirname, '.locks')
        locks_manager = LocksManager.create('fasteners', locks_directory=locks_directory)
        db_filename = os.path.join(tmpdirname, 'cache.sqlite3')
        cache = CacheImplementation.create('sqlite3', tmpdirname, locks_manager,
                                           filename=db_filename)
        yield cache


@pytest.fixture(params=['cache_memory', 'cache_sqlite3', 'cache_sqlite3_fasteners'])
def cache_implementation(request) -> CacheImplementation:
    # These fixtures will parameterize tests that use it with all database backends
    return request.getfixturevalue(request.param)


@pytest.fixture(params=['cache_memory', 'cache_sqlite3', 'cache_sqlite3_fasteners'])
def cache_1level(request) -> Cache:
    # These fixtures will parameterize tests that use it with all database backends
    return request.getfixturevalue(request.param)


@pytest.fixture
def cache_2level() -> Cache:
    # TODO: Implement some kind of factory
    # Retrieve a 2-level cache based on sqlite3 and fasteners
    with tempfile.TemporaryDirectory(suffix='-ws-cache') as wstmpdirname:
        with tempfile.TemporaryDirectory(suffix='-user-cache') as usertmpdirname:
            locks_directory = os.path.join(usertmpdirname, '.locks')
            locks_manager = LocksManager.create('fasteners', locks_directory=locks_directory)

            db_ws_filename = os.path.join(wstmpdirname, 'cache.sqlite3')
            ws_cache = CacheImplementation.create('sqlite3', wstmpdirname, locks_manager,
                                                  filename=db_ws_filename)

            db_user_filename = os.path.join(usertmpdirname, 'cache.sqlite3')
            user_cache = CacheImplementation.create('sqlite3', usertmpdirname, locks_manager,
                                                    filename=db_user_filename)

            cache = CacheTwoLevels(ws_cache, user_cache, locks_manager)
            yield cache
