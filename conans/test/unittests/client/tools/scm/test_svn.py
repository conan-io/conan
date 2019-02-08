# coding=utf-8

import unittest

from mock import patch

from conans.client.tools.scm import SVN
from conans.test.utils.tools import temp_folder


class SVNRemoteUrlTest(unittest.TestCase):

    def test_remove_credentials(self):
        """ Check that the 'remove_credentials' argument is taken into account """
        expected_url = 'https://myrepo.com/path/to/repo'
        origin_url = 'https://username:password@myrepo.com/path/to/repo'

        svn = SVN(folder=temp_folder())

        # Mocking, as we cannot change SVN remote to a non-existing url
        with patch.object(svn, '_show_item', return_value=origin_url):
            self.assertEqual(svn.get_remote_url(), origin_url)
            self.assertEqual(svn.get_remote_url(remove_credentials=True), expected_url)
