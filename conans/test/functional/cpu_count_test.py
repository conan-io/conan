import unittest
from conans.test.utils.tools import TestClient
from conans.paths import CONANFILE


conanfile = """
from conans import ConanFile, tools

class AConan(ConanFile):
    name = "Hello0"
    version = "0.1"

    def build(self):
        self.output.warn("CPU COUNT=> %s" % tools.cpu_count())

"""


class CPUCountTest(unittest.TestCase):

    def cpu_count_override_test(self):
        self.client = TestClient()
        self.client.save({CONANFILE: conanfile})
        self.client.run("config set general.cpu_count=5")
        self.client.run("export lasote/stable")
        self.client.run("install Hello0/0.1@lasote/stable --build missing")
        self.assertIn("CPU COUNT=> 5", self.client.user_io.out)
