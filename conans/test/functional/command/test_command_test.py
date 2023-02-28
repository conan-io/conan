import os
import platform
import time
import unittest

import pytest

from conans.test.utils.tools import TestClient


@pytest.mark.xfail(reason="cmake old generator will be removed")
@pytest.mark.slow
class ConanTestTest(unittest.TestCase):

    @pytest.mark.tool("cmake")
    def test_conan_test(self):
        client = TestClient()
        client.run("new cmake_lib -d name=hello -d version=0.1")

        client.run("create . --user=lasote --channel=stable -tf=")
        time.sleep(1)  # Try to avoid windows errors in CI  (Cannot change permissions)
        client.run("test test_package hello/0.1@lasote/stable -s build_type=Release")
        self.assertIn('hello/0.1: Hello World Release!', client.out)

        self.assertNotIn("WARN: conanenv.txt file not found", client.out)

        client.run("test test_package hello/0.1@lasote/stable -s hello/*:build_type=Debug "
                   "--build missing")
        self.assertIn('hello/0.1: Hello World Debug!', client.out)
        subfolder = "Release" if platform.system() != "Windows" else ""
        assert os.path.exists(os.path.join(client.current_folder, "test_package",
                                           "build", subfolder, "generators", "conaninfo.txt"))
