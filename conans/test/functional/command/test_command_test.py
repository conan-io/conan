import os
import platform
import textwrap
import time
import unittest

import pytest

from conans.test.utils.tools import TestClient
from conans.util.files import mkdir
from utils.test_files import temp_folder


@pytest.mark.slow
class ConanTestTest(unittest.TestCase):

    @pytest.mark.tool_cmake
    def test_conan_test(self):
        client = TestClient()
        client.run("new hello/0.1 -m=cmake_lib")

        client.run("create . lasote/stable -tf=None")
        time.sleep(1)  # Try to avoid windows errors in CI  (Cannot change permissions)
        client.run("test test_package hello/0.1@lasote/stable -s build_type=Release")
        self.assertIn('hello/0.1: Hello World Release!', client.out)

        self.assertNotIn("WARN: conanbuildinfo.txt file not found", client.out)
        self.assertNotIn("WARN: conanenv.txt file not found", client.out)

        client.run("test test_package hello/0.1@lasote/stable -s hello:build_type=Debug "
                   "--build missing")
        self.assertIn('hello/0.1: Hello World Debug!', client.out)
        subfolder = "Release" if platform.system() != "Windows" else ""
        assert os.path.exists(os.path.join(client.current_folder, "test_package",
                                           "build", subfolder, "generators", "conaninfo.txt"))

    def test_whateverrr(self):
        tc = TestClient()
        tc.run("new hello/1.0 -m=cmake_lib")
        test_root_folder_output = temp_folder()
        tc.run(f"create . hello/1.0@ -c user.test_build_folder='{test_root_folder_output}'")
        os.listdir(test_root_folder_output)
