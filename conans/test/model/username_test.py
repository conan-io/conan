import unittest

from conans.errors import ConanException
from conans.model.username import Username


class UsernameTest(unittest.TestCase):

    def username_test(self):
        Username("userwith-hypens")
        self.assertRaises(ConanException, Username, "")
        self.assertRaises(ConanException, Username, "A"*31)
        Username("A"*30)

        self.assertRaises(ConanException, Username, "1A")
        self.assertRaises(ConanException, Username, "_A")
        Username("A1")
        Username("a_")

        self.assertRaises(ConanException, Username, "$$")