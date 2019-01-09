# coding=utf-8

import unittest

from conans.client.tools.scm import SCMBase


class RemoveCredentialsTest(unittest.TestCase):

    def test_http(self):
        expected_url = 'https://myrepo.com/path/to/repo.git'
        test_urls = ['https://myrepo.com/path/to/repo.git',
                     'https://username:password@myrepo.com/path/to/repo.git',
                     'https://username@myrepo.com/path/to/repo.git',
                     'https://gitlab-ci-token:1324@myrepo.com/path/to/repo.git',
                     ]

        for it in test_urls:
            self.assertEqual(expected_url, SCMBase._remove_credentials_url(it))

    def test_http_with_port_number(self):
        self.assertEqual('https://myrepo.com:8000/path/to/repo.git',
                         SCMBase._remove_credentials_url(
                             'https://username@myrepo.com:8000/path/to/repo.git'))

    def test_ssh(self):
        # Here, for ssh, we don't want to remove the user ('git' in this example)
        self.assertEqual('git@github.com:conan-io/conan.git',
                         SCMBase._remove_credentials_url(
                             'git@github.com:conan-io/conan.git'))

    def test_local_unix(self):
        self.assertEqual('file:///srv/git/project.git',
                         SCMBase._remove_credentials_url('file:///srv/git/project.git'))
        self.assertEqual('file:///srv/git/PROJECT.git',
                         SCMBase._remove_credentials_url('file:///srv/git/PROJECT.git'))

    def test_local_windows(self):
        self.assertEqual('file:///c:/srv/git/PROJECT',
                         SCMBase._remove_credentials_url('file:///c:/srv/git/PROJECT'))
        self.assertEqual('file:///C:/srv/git/PROJECT',
                         SCMBase._remove_credentials_url('file:///C:/srv/git/PROJECT'))

    def test_svn_ssh(self):
        self.assertEqual('svn+ssh://10.106.191.164/home/svn/shproject',
                         SCMBase._remove_credentials_url(
                             'svn+ssh://username:password@10.106.191.164/home/svn/shproject'))