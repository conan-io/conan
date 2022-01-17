import textwrap
import unittest

import pytest

from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient

conanfile = """
from conans import ConanFile, tools

class AConan(ConanFile):
    name = "hello0"
    version = "0.1"

    def build(self):
        self.output.warning("CPU COUNT=> %s" % tools.cpu_count())

"""


@pytest.mark.xfail(reason="Legacy conan.conf configuration")
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
        client.run("export . --user=lasote --channel=stable")
        client.run("install --reference=hello0/0.1@lasote/stable --build missing")
        self.assertIn("CPU COUNT=> 5", client.out)
