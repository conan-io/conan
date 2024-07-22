import os
import unittest

from conan.internal.api.remotes.localdb import LocalDB
from conan.test.utils.test_files import temp_folder


class LocalStoreTest(unittest.TestCase):

    def test_localdb(self):
        tmp_dir = temp_folder()
        db_file = os.path.join(tmp_dir, "dbfile")
        localdb = LocalDB(db_file)

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
