# coding=utf-8

import unittest
import textwrap
from parameterized import parameterized
from conans.test.utils.tools import TestClient, create_local_git_repo


class ExportCommandTestCase(unittest.TestCase):
    conanfile = textwrap.dedent("""\
        from conans import ConanFile

        class Lib(ConanFile):
            scm = {{"type": "git",
                    "url": "{url_value}",
                    "revision": "{rev_value}"}}
    """)

    @parameterized.expand([(True, False), (False, True)])
    def test_no_git_repo(self, auto_url, auto_rev):
        url_value = "auto" if auto_url else "http://this.url"
        rev_value = "auto" if auto_rev else "123"

        self.client = TestClient()
        self.client.save({"conanfile.py": self.conanfile.format(url_value=url_value,
                                                                rev_value=rev_value)
                          })
        self.client.run("export . lib/version@user/channel", assert_error=True)
        self.assertIn("ERROR: Not a valid git repository", self.client.out)

    @parameterized.expand([(True, False), (False, True)])
    def test_non_existing_remote(self, auto_url, auto_rev):
        url_value = "auto" if auto_url else "http://this.url"
        rev_value = "auto" if auto_rev else "123"

        self.path, _ = create_local_git_repo({"conanfile.py":
                                              self.conanfile.format(url_value=url_value,
                                                                    rev_value=rev_value)})
        self.client = TestClient()
        self.client.current_folder = self.path
        self.client.run("export . lib/version@user/channel", assert_error=True)
        self.assertIn("ERROR: Repo origin cannot be deduced", self.client.out)

