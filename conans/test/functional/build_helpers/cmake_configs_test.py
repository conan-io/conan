import os
import unittest

from nose.plugins.attrib import attr

from conans.test.utils.multi_config import multi_config_files
from conans.test.utils.tools import TestClient


@attr("slow")
class CMakeConfigsTest(unittest.TestCase):

    def test_package_configs_test(self):
        client = TestClient()
        name = "Hello0"
        files = multi_config_files(name, test=True)
        client.save(files, clean_first=True)

        client.run("create . user/testing")
        self.assertIn("Hello Release Hello0", client.out)
        self.assertIn("Hello Debug Hello0", client.out)

    def cmake_multi_test(self):
        client = TestClient()

        deps = None
        for name in ["Hello0", "Hello1", "Hello2"]:
            files = multi_config_files(name, test=False, deps=deps)
            client.save(files, clean_first=True)
            deps = [name]
            if name != "Hello2":
                client.run("export . lasote/stable")

        client.run('install . --build missing')
        client.run("build .")
        cmd = os.sep.join([".", "bin", "say_hello"])
        client.run_command(cmd)
        self.assertIn("Hello Release Hello2 Hello Release Hello1 Hello Release Hello0",
                      " ".join(str(client.out).splitlines()))
        client.run_command(cmd + "_d")
        self.assertIn("Hello Debug Hello2 Hello Debug Hello1 Hello Debug Hello0",
                      " ".join(str(client.out).splitlines()))
