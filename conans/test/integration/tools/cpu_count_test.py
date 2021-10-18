import textwrap
import unittest

from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient

conanfile = """
from conans import ConanFile, tools

class AConan(ConanFile):
    name = "Hello0"
    version = "0.1"

    def build(self):
        self.output.warning("CPU COUNT=> %s" % tools.cpu_count())

"""


class CPUCountTest(unittest.TestCase):

    def test_cpu_count_override(self):
        client = TestClient()
        client.save({CONANFILE: conanfile})
        conan_conf = textwrap.dedent("""
                        [storage]
                        path = ./data
                        [general]
                        cpu_count=5
                """.format())
        client.save({"conan.conf": conan_conf}, path=client.cache.cache_folder)
        client.run("export . lasote/stable")
        client.run("install Hello0/0.1@lasote/stable --build missing")
        self.assertIn("CPU COUNT=> 5", client.out)
