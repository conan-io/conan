# coding=utf-8

import itertools
import textwrap
import unittest

import pytest
from parameterized import parameterized

from conans.test.utils.scm import create_local_git_repo
from conans.test.utils.tools import TestClient


@pytest.mark.tool("svn")
class ExportErrorCommandTestCase(unittest.TestCase):
    conanfile = textwrap.dedent("""\
        from conan import ConanFile

        class Lib(ConanFile):
            scm = {{"type": "{repo_type}",
                    "url": "{url_value}",
                    "revision": "{rev_value}"}}
    """)

    @parameterized.expand(itertools.product(["SVN", "git"],))
    def test_no_repo(self, repo_type):
        url_value = "auto"
        rev_value = "auto"

        self.client = TestClient()
        self.client.save({"conanfile.py": self.conanfile.format(repo_type=repo_type.lower(),
                                                                url_value=url_value,
                                                                rev_value=rev_value)
                          })
        self.client.run("export . --name=lib --version=version --user=user --channel=channel", assert_error=True)
        self.assertIn("ERROR: '{}' is not a valid '{}' repository".format(
                      self.client.current_folder, repo_type.lower()), self.client.out)


@pytest.mark.tool("git")
class ExportCommandTestCase(unittest.TestCase):
    conanfile = textwrap.dedent("""\
        from conan import ConanFile

        class Lib(ConanFile):
            scm = {{"type": "{repo_type}",
                    "url": "{url_value}",
                    "revision": "{rev_value}"}}
    """)

    def test_non_existing_remote(self):
        url_value = "auto"
        rev_value = "auto"

        self.path, _ = create_local_git_repo({"conanfile.py":
                                              self.conanfile.format(repo_type="git",
                                                                    url_value=url_value,
                                                                    rev_value=rev_value)})
        self.client = TestClient()
        self.client.current_folder = self.path
        self.client.run("export . --name=lib --version=version --user=user --channel=channel")

        self.assertIn("WARN: Repo origin cannot be deduced, 'auto' fields won't be replaced.",
                      self.client.out)
