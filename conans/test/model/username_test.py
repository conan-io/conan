import unittest

from conans.errors import ConanException
from conans.model.username import Username


class UsernameTest(unittest.TestCase):

    def username_test(self):
        Username("userwith-hypens")
        self.assertRaises(ConanException, Username, "")
        self.assertRaises(ConanException, Username, "a")
        self.assertRaises(ConanException, Username, "A"*52)
        Username("A"*30)

        self.assertRaises(ConanException, Username, "-A")
        self.assertRaises(ConanException, Username, "&A")
        Username("A1")
        Username("1A")
        Username("_A")
        Username("a_")

        self.assertRaises(ConanException, Username, "$$")
