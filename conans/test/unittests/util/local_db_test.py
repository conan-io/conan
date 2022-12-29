import os
import unittest
import uuid

import six
import pytest

from conans.client.store.localdb import LocalDB
from conans.test.utils.test_files import temp_folder


class LocalStoreTest(unittest.TestCase):

    def test_localdb(self):
        tmp_dir = temp_folder()
        db_file = os.path.join(tmp_dir, "dbfile")
        localdb = LocalDB.create(db_file)

        # Test write and read login
        user, token, access_token = localdb.get_login("myurl1")
        self.assertIsNone(user)
        self.assertIsNone(token)
        self.assertIsNone(access_token)

        localdb.store("pepe", "token", "access_token", "myurl1")
        user, token, access_token = localdb.get_login("myurl1")
        self.assertEqual("pepe", user)
        self.assertEqual("token", token)
        self.assertEqual("access_token", access_token)
        self.assertEqual("pepe", localdb.get_username("myurl1"))

    def test_token_encryption_ascii(self):
        tmp_dir = temp_folder()
        db_file = os.path.join(tmp_dir, "dbfile")
        encryption_key = str(uuid.uuid4())
        localdb = LocalDB.create(db_file, encryption_key=encryption_key)

        localdb.store("pepe", "token", "access_token", "myurl1")
        user, token, access_token = localdb.get_login("myurl1")
        self.assertEqual("pepe", user)
        self.assertEqual("token", token)
        self.assertEqual("access_token", access_token)

    def test_token_encryption_none(self):
        tmp_dir = temp_folder()
        db_file = os.path.join(tmp_dir, "dbfile")
        encryption_key = str(uuid.uuid4())
        localdb = LocalDB.create(db_file, encryption_key=encryption_key)

        localdb.store("pepe", "token", None, "myurl1")
        user, token, access_token = localdb.get_login("myurl1")
        self.assertEqual("pepe", user)
        self.assertEqual("token", token)
        self.assertEqual(None, access_token)

    @pytest.mark.skipif(six.PY2, reason="Python2 sqlite3 converts to str")
    def test_token_encryption_unicode(self):
        tmp_dir = temp_folder()
        db_file = os.path.join(tmp_dir, "dbfile")
        encryption_key = str(uuid.uuid4())
        localdb = LocalDB.create(db_file, encryption_key=encryption_key)

        token_input = b'espa\xc3\xb1a\xe2\x82\xac$'.decode('utf-8')  # Only ASCII files in codebase
        localdb.store("pepe", token_input, token_input, "myurl1")
        user, token, access_token = localdb.get_login("myurl1")
        self.assertEqual("pepe", user)
        self.assertEqual(token_input, token)
        self.assertEqual(token_input, access_token)
        self.assertEqual("pepe", localdb.get_username("myurl1"))

        # Without the encryption key we get obfuscated values
        other_db = LocalDB.create(db_file)
        user, token, access_token = other_db.get_login("myurl1")
        self.assertEqual("pepe", user)
        self.assertNotEqual(token_input, token)
        self.assertNotEqual(token_input, access_token)
