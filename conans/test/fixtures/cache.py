import os
import tempfile

import pytest

from conan.cache.cache import Cache
from conan.cache.cache_implementation import CacheImplementation
from conan.locks.locks_manager import LocksManager


@pytest.fixture
def cache_memory() -> Cache:
    locks_manager = LocksManager.create('memory')
    with tempfile.TemporaryDirectory() as tmpdirname:
        cache = CacheImplementation.create('memory', tmpdirname, locks_manager)
        yield cache


@pytest.fixture
def cache_sqlite3() -> Cache:
    with tempfile.TemporaryDirectory() as tmpdirname:
        db_filename = os.path.join(tmpdirname, 'locks.sqlite3')
        locks_manager = LocksManager.create('sqlite3', filename=db_filename)
        cache = CacheImplementation.create('sqlite3', tmpdirname, locks_manager, filename=db_filename)
        yield cache


@pytest.fixture
def cache_sqlite3_fasteners() -> Cache:
    with tempfile.TemporaryDirectory() as tmpdirname:
        locks_directory = os.path.join(tmpdirname, '.locks')
        locks_manager = LocksManager.create('fasteners', locks_directory=locks_directory)
        db_filename = os.path.join(tmpdirname, 'cache.sqlite3')
        cache = CacheImplementation.create('sqlite3', tmpdirname, locks_manager, filename=db_filename)
        yield cache


@pytest.fixture(params=['cache_memory', 'cache_sqlite3', 'cache_sqlite3_fasteners'])
def cache(request) -> Cache:
    # These fixtures will parameterize tests that use it with all database backends
    return request.getfixturevalue(request.param)
