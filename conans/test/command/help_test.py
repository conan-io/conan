import unittest
from conans.test.utils.tools import TestClient


class BasicTest(unittest.TestCase):

    def help_test(self):
        conan = TestClient()
        conan.run("")
        self.assertIn('Conan commands. Type $conan "command" -h', conan.user_io.out)
