# coding=utf-8

import unittest

from conans.client.tools.scm import Git
from conans.test.utils.tools import temp_folder


class GitRemoteUrlTest(unittest.TestCase):

    def test_remove_credentials(self):
        """ Check that the 'remove_credentials' argument is taken into account """
        expected_url = 'https://myrepo.com/path/to/repo.git'
        origin_url = 'https://username:password@myrepo.com/path/to/repo.git'

        git = Git(folder=temp_folder())
        git.run("init .")
        git.run("remote add origin {}".format(origin_url))

        self.assertEqual(git.get_remote_url(), origin_url)
        self.assertEqual(git.get_remote_url(remove_credentials=True), expected_url)
