# coding=utf-8

import tempfile
import unittest

from mock import mock

from conans.errors import ConanException
from conans.model.scm import SCM


class SCMDetectRepoTest(unittest.TestCase):

    def setUp(self):
        self.folder = tempfile.gettempdir()
        # Be sure there is no repo in the folder to test
        for name, candidate in SCM.availables.items():
            try:
                candidate(folder=self.folder).check_repo()
            except ConanException:
                pass
            else:
                self.fail("There is a repo of type '{}' in the folder to test".format(name))

    def test_svn(self):
        with mock.patch("conans.client.tools.scm.SVN.check_repo", return_value=None):
            r = SCM.detect_scm(folder=self.folder)
            self.assertEqual(r, "svn")

    def test_git(self):
        with mock.patch("conans.client.tools.scm.Git.check_repo", return_value=None):
            r = SCM.detect_scm(folder=self.folder)
            self.assertEqual(r, "git")

    def test_none(self):
        r = SCM.detect_scm(folder=self.folder)
        self.assertEqual(r, None)
