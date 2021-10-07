# coding=utf-8

import itertools
import textwrap
import unittest

import pytest
from parameterized import parameterized

from conans.test.utils.scm import create_local_git_repo
from conans.test.utils.tools import TestClient


@pytest.mark.tool_svn
class ExportErrorCommandTestCase(unittest.TestCase):
    conanfile = textwrap.dedent("""\
        from conans import ConanFile

        class Lib(ConanFile):
            scm = {{"type": "{repo_type}",
                    "url": "{url_value}",
                    "revision": "{rev_value}"}}
    """)

    @parameterized.expand(itertools.product(["SVN", "git"], [(True, False), (False, True)]))
    def test_no_repo(self, repo_type, autos):
        auto_url, auto_rev = autos
        url_value = "auto" if auto_url else "http://this.url"
        rev_value = "auto" if auto_rev else "123"

        self.client = TestClient()
        self.client.save({"conanfile.py": self.conanfile.format(repo_type=repo_type.lower(),
                                                                url_value=url_value,
                                                                rev_value=rev_value)
                          })
        self.client.run("export . lib/version@user/channel", assert_error=True)
        self.assertIn("ERROR: '{}' is not a valid '{}' repository".format(
                      self.client.current_folder, repo_type.lower()), self.client.out)


@pytest.mark.tool_git
class ExportCommandTestCase(unittest.TestCase):
    conanfile = textwrap.dedent("""\
        from conans import ConanFile

        class Lib(ConanFile):
            scm = {{"type": "{repo_type}",
                    "url": "{url_value}",
                    "revision": "{rev_value}"}}
    """)

    @parameterized.expand([(True, False), (False, True)])
    def test_non_existing_remote(self, auto_url, auto_rev):
        url_value = "auto" if auto_url else "http://this.url"
        rev_value = "auto" if auto_rev else "123"

        self.path, _ = create_local_git_repo({"conanfile.py":
                                              self.conanfile.format(repo_type="git",
                                                                    url_value=url_value,
                                                                    rev_value=rev_value)})
        self.client = TestClient()
        self.client.current_folder = self.path
        self.client.run("export . lib/version@user/channel")
        if auto_url:
            self.assertIn("WARN: Repo origin cannot be deduced, 'auto' fields won't be replaced.",
                          self.client.out)
