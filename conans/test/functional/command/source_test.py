import os
import unittest

import pytest

from conans.test.utils.tools import TestClient


class SourceTest(unittest.TestCase):

    @pytest.mark.tool_git
    def test_conanfile_removed(self):
        # https://github.com/conan-io/conan/issues/4013
        conanfile = """from conans import ConanFile
class ScmtestConan(ConanFile):
    scm = {
        "type": "git",
        "url": "auto",
        "revision": "auto"
    }
"""
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run_command("git init .")
        client.run("source .")
        self.assertEqual(sorted(["conanfile.py", '.git']),
                         sorted(os.listdir(client.current_folder)))
