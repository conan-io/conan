import unittest
from conans.test.utils.tools import TestClient
from nose.plugins.attrib import attr
import os
from conans.test.utils.multi_config import multi_config_files


@attr("slow")
class CMakeConfigsTest(unittest.TestCase):

    def test_package_configs_test(self):
        client = TestClient()
        name = "Hello0"
        files = multi_config_files(name, test=True)
        client.save(files, clean_first=True)

        client.run("test_package")
        self.assertIn("Hello Release Hello0", client.user_io.out)
        self.assertIn("Hello Debug Hello0", client.user_io.out)

    def cmake_multi_test(self):
        client = TestClient()

        deps = None
        for name in ["Hello0", "Hello1", "Hello2"]:
            files = multi_config_files(name, test=False, deps=deps)
            client.save(files, clean_first=True)
            deps = [name]
            if name != "Hello2":
                client.run("export lasote/stable")

        client.run('install . --build missing')
        client.run("build")
        cmd = os.sep.join([".", "bin", "say_hello"])
        client.runner(cmd, cwd=client.current_folder)
        self.assertIn("Hello Release Hello2 Hello Release Hello1 Hello Release Hello0",
                      " ".join(str(client.user_io.out).splitlines()))
        client.runner(cmd + "_d", cwd=client.current_folder)
        self.assertIn("Hello Debug Hello2 Hello Debug Hello1 Hello Debug Hello0",
                      " ".join(str(client.user_io.out).splitlines()))
