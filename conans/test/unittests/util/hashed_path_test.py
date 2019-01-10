import os
import unittest

from conans.test.utils.test_files import temp_folder

from conans.util.windows import hashed_redirect


class HashedPathTest(unittest.TestCase):
    def setUp(self):
        self.path = "package_name/version/user/channel/export"
        self.folder = temp_folder()

    def test_creates_deterministic_path(self):
        first = hashed_redirect(self.folder, self.path)
        second = hashed_redirect(self.folder, self.path)
        self.assertEqual(first, second)

    def test_avoids_collisions(self):
        first = hashed_redirect(self.folder, self.path)
        os.mkdir(first)

        second = hashed_redirect(self.folder, self.path)
        self.assertLess(len(first), len(second))

    def test_give_up_if_cannot_avoid_collisions(self):
        # Make two attempts to generate distinct path names
        os.mkdir(hashed_redirect(self.folder, self.path))
        os.mkdir(hashed_redirect(self.folder, self.path))

        # The two attempts were already spent, so the following should give up
        redirect = hashed_redirect(self.folder, self.path, attempts=2)
        self.assertEqual(None, redirect)
