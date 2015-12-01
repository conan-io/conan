import unittest
from conans.client.store.localdb import LocalDB
import os
from conans.test.utils.test_files import temp_folder


class LocalStoreTest(unittest.TestCase):

    def localdb_test(self):
        tmp_dir = temp_folder()
        db_file = os.path.join(tmp_dir, "dbfile")
        localdb = LocalDB(db_file)

        # Test write and read login
        localdb.init()
        login, token = localdb.get_login()
        self.assertIsNone(login)
        self.assertIsNone(token)

        localdb.set_login(("pepe", "token"))
        login, token = localdb.get_login()
        self.assertEquals("pepe", login)
        self.assertEquals("token", token)
        self.assertEquals("pepe", localdb.get_username())
