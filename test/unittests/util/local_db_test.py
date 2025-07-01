import os

from conan.internal.api.remotes.localdb import LocalDB
from conan.test.utils.test_files import temp_folder


def test_localdb():
    tmp_dir = temp_folder()
    db_file = os.path.join(tmp_dir, "dbfile")
    localdb = LocalDB(db_file)

    # Test write and read login
    user, token, access_token = localdb.get_login("myurl1")
    assert user is None
    assert token is None
    assert access_token is None

    localdb.store("pepe", "token", "access_token", "myurl1")
    user, token, access_token = localdb.get_login("myurl1")
    assert user == "pepe"
    assert token == "token"
    assert access_token == "access_token"
    assert "pepe" == localdb.get_username("myurl1")
