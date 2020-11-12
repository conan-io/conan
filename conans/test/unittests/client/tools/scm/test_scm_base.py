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
        # URL-like syntax
        self.assertEqual('ssh://git@github.com:2222/conan-io/conan.git',
                         SCMBase._remove_credentials_url(
                             'ssh://git@github.com:2222/conan-io/conan.git'))
        # URL-like syntax with a password
        self.assertEqual('ssh://git@github.com:2222/conan-io/conan.git',
                         SCMBase._remove_credentials_url(
                             'ssh://git:password@github.com:2222/conan-io/conan.git'))
        self.assertEqual('ssh://github.com:2222/conan-io/conan.git',
                         SCMBase._remove_credentials_url(
                             'ssh://github.com:2222/conan-io/conan.git'))
        # scp-like syntax
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


class OutputMock(object):

    def __init__(self):
        self.out = list()

    def warn(self, text):
        self.out.append("WARN: " + text)


class GetUrlWithCredentialsTest(unittest.TestCase):

    def test_ssh(self):
        scm = SCMBase()
        self.assertEqual('ssh://github.com/conan-io/conan.git',
                         scm.get_url_with_credentials("ssh://github.com/conan-io/conan.git"))

    def test_ssh_username_password(self):
        scm = SCMBase(username="dani", password="pass")
        self.assertEqual('ssh://dani:pass@github.com/conan-io/conan.git',
                         scm.get_url_with_credentials("ssh://github.com/conan-io/conan.git"))

    def test_ssh_username(self):
        scm = SCMBase(username="dani")
        self.assertEqual('ssh://dani@github.com/conan-io/conan.git',
                         scm.get_url_with_credentials("ssh://github.com/conan-io/conan.git"))

    def test_ssh_password(self):
        output = OutputMock()
        scm = SCMBase(password="pass", output=output)
        self.assertEqual('ssh://github.com/conan-io/conan.git',
                         scm.get_url_with_credentials("ssh://github.com/conan-io/conan.git"))
        self.assertIn("WARN: SCM username undefined, ignoring 'password' parameter", output.out)

    def test_ssh_url_with_username_only_password(self):
        scm = SCMBase(password="pass")
        self.assertEqual('ssh://git:pass@github.com/conan-io/conan.git',
                         scm.get_url_with_credentials("ssh://git@github.com/conan-io/conan.git"))

    def test_ssh_url_with_username_only_username(self):
        output = OutputMock()
        scm = SCMBase(username="dani", output=output)
        self.assertEqual('ssh://git@github.com/conan-io/conan.git',
                         scm.get_url_with_credentials("ssh://git@github.com/conan-io/conan.git"))
        self.assertIn("WARN: SCM username got from URL, ignoring 'username' parameter", output.out)

    def test_ssh_url_with_username_and_username_password(self):
        output = OutputMock()
        scm = SCMBase(password="pass", username="dani", output=output)
        self.assertEqual('ssh://git:pass@github.com/conan-io/conan.git',
                         scm.get_url_with_credentials("ssh://git@github.com/conan-io/conan.git"))
        self.assertIn("WARN: SCM username got from URL, ignoring 'username' parameter", output.out)

    def test_ssh_url_with_username_password_and_only_password(self):
        output = OutputMock()
        scm = SCMBase(password="password", output=output)
        self.assertEqual('ssh://git:pass@github.com/conan-io/conan.git',
                         scm.get_url_with_credentials("ssh://git:pass@github.com/conan-io/conan.git"))
        self.assertIn("WARN: SCM password got from URL, ignoring 'password' parameter", output.out)

    def test_ssh_url_with_username_password_and_only_username(self):
        output = OutputMock()
        scm = SCMBase(username="dani", output=output)
        self.assertEqual('ssh://git:pass@github.com/conan-io/conan.git',
                         scm.get_url_with_credentials("ssh://git:pass@github.com/conan-io/conan.git"))
        self.assertIn("WARN: SCM username got from URL, ignoring 'username' parameter", output.out)

    def test_ssh_url_with_username_password_and_username_password(self):
        output = OutputMock()
        scm = SCMBase(password="password", username="dani", output=output)
        self.assertEqual('ssh://git:pass@github.com/conan-io/conan.git',
                         scm.get_url_with_credentials("ssh://git:pass@github.com/conan-io/conan.git"))
        self.assertIn("WARN: SCM username got from URL, ignoring 'username' parameter", output.out)
        self.assertIn("WARN: SCM password got from URL, ignoring 'password' parameter", output.out)
