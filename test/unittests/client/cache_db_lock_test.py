import os
from unittest import mock

import pytest

from conan.internal.cache.db.recipes_table import RecipesDBTable
from conan.test.utils.test_files import temp_folder


def _table():
    return RecipesDBTable(os.path.join(temp_folder(), "cache.sqlite3"))


def test_lock_released_if_connect_fails():
    table = _table()
    with mock.patch("sqlite3.connect", side_effect=OSError("connect failed")):
        with pytest.raises(OSError, match="connect failed"):
            with table.db_connection():
                pass
    assert not table._lock.locked()
    table.create_table()  # The DB is still usable


def test_lock_released_if_close_fails():
    table = _table()
    connection = mock.MagicMock()
    connection.close.side_effect = OSError("close failed")
    with mock.patch("sqlite3.connect", return_value=connection):
        with pytest.raises(OSError, match="close failed"):
            with table.db_connection():
                pass
    assert not table._lock.locked()
    table.create_table()  # The DB is still usable
