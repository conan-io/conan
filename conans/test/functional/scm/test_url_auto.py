# coding=utf-8

import textwrap
import unittest

import pytest

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient
from conans.test.utils.scm import create_local_git_repo


class RemoveCredentials(unittest.TestCase):

    conanfile = textwrap.dedent("""\
        from conans import ConanFile

        class Lib(ConanFile):
            scm = {"type": "git", "url": "auto"}

    """)

    def setUp(self):
        self.ref = ConanFileReference.loads("lib/1.0@lasote/testing")
        self.path, _ = create_local_git_repo({"conanfile.py": self.conanfile})
        self.client = TestClient()
        self.client.current_folder = self.path
        self.client.run_command("git remote add origin https://url.to.be.sustituted")

    @pytest.mark.tool_git
    def test_https(self):
        expected_url = 'https://myrepo.com.git'
        origin_url = 'https://username:password@myrepo.com.git'
        self.client.run_command("git remote set-url origin {}".format(origin_url))
        self.client.run("export . {}".format(self.ref))
        self.assertIn("Repo origin deduced by 'auto': {}".format(expected_url), self.client.out)
