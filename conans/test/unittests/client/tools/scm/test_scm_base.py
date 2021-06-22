# coding=utf-8

import unittest

from conans.client.tools.scm import SCMBase
from conans.errors import ConanException


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

    def test_url(self):
        scm = SCMBase()
        self.assertEqual('http://github.com/conan-io/conan.git',
                         scm.get_url_with_credentials("http://github.com/conan-io/conan.git"))

    def test_url_username(self):
        scm = SCMBase()
        self.assertEqual('http://user@github.com/conan-io/conan.git',
                         scm.get_url_with_credentials("http://user@github.com/conan-io/conan.git"))

    def test_url_password(self):
        scm = SCMBase()
        self.assertEqual('http://user:pass@github.com/conan-io/conan.git',
                         scm.get_url_with_credentials(
                             "http://user:pass@github.com/conan-io/conan.git"))

    def test_url_with_user_param(self):
        scm = SCMBase(username="user")
        self.assertEqual('https://user@github.com/conan-io/conan.git',
                         scm.get_url_with_credentials("https://github.com/conan-io/conan.git"))

    def test_url_with_password_param(self):
        scm = SCMBase(password="pass")
        self.assertEqual('https://github.com/conan-io/conan.git',
                         scm.get_url_with_credentials("https://github.com/conan-io/conan.git"))

    def test_url_with_user_password_param(self):
        scm = SCMBase(username="user", password="pass")
        self.assertEqual('https://user:pass@github.com/conan-io/conan.git',
                         scm.get_url_with_credentials("https://github.com/conan-io/conan.git"))

    def test_url_with_user_password_characters_param(self):
        scm = SCMBase(username="el niño", password="la contra%seña")
        self.assertEqual('https://el+ni%C3%B1o:la+contra%25se%C3%B1a@github.com/conan-io/conan.git',
                         scm.get_url_with_credentials("https://github.com/conan-io/conan.git"))

    def test_url_user_with_user_param(self):
        output = OutputMock()
        scm = SCMBase(username="user", output=output)
        self.assertEqual('https://dani@github.com/conan-io/conan.git',
                         scm.get_url_with_credentials("https://dani@github.com/conan-io/conan.git"))
        self.assertEqual(1, len(output.out))
        self.assertIn("WARN: SCM username got from URL, ignoring 'username' parameter", output.out)

    def test_url_user_with_password_param(self):
        scm = SCMBase(password="pass")
        self.assertEqual('https://dani:pass@github.com/conan-io/conan.git',
                         scm.get_url_with_credentials("https://dani@github.com/conan-io/conan.git"))

    def test_url_user_with_user_password_param(self):
        output = OutputMock()
        scm = SCMBase(username="user", password="pass", output=output)
        self.assertEqual('https://dani:pass@github.com/conan-io/conan.git',
                         scm.get_url_with_credentials("https://dani@github.com/conan-io/conan.git"))
        self.assertEqual(1, len(output.out))
        self.assertIn("WARN: SCM username got from URL, ignoring 'username' parameter", output.out)

    def test_url_user_pass_with_user_param(self):
        output = OutputMock()
        scm = SCMBase(username="user", output=output)
        self.assertEqual('http://dani:pass@github.com/conan-io/conan.git',
                         scm.get_url_with_credentials(
                             "http://dani:pass@github.com/conan-io/conan.git"))
        self.assertEqual(1, len(output.out))
        self.assertIn("WARN: SCM username got from URL, ignoring 'username' parameter", output.out)

    def test_url_user_pass_with_password_param(self):
        output = OutputMock()
        scm = SCMBase(password="pass", output=output)
        self.assertEqual('http://dani:secret@github.com/conan-io/conan.git',
                         scm.get_url_with_credentials(
                             "http://dani:secret@github.com/conan-io/conan.git"))
        self.assertEqual(1, len(output.out))
        self.assertIn("WARN: SCM password got from URL, ignoring 'password' parameter", output.out)

    def test_url_user_pass_with_user_password_param(self):
        output = OutputMock()
        scm = SCMBase(username="user", password="pass", output=output)
        self.assertEqual('http://dani:secret@github.com/conan-io/conan.git',
                         scm.get_url_with_credentials(
                             "http://dani:secret@github.com/conan-io/conan.git"))
        self.assertEqual(2, len(output.out))
        self.assertIn("WARN: SCM username got from URL, ignoring 'username' parameter", output.out)
        self.assertIn("WARN: SCM password got from URL, ignoring 'password' parameter", output.out)

    def test_ssh(self):
        scm = SCMBase()
        self.assertEqual('ssh://github.com/conan-io/conan.git',
                         scm.get_url_with_credentials("ssh://github.com/conan-io/conan.git"))

    def test_ssh_username_password(self):
        output = OutputMock()
        scm = SCMBase(username="dani", password="pass", output=output)
        self.assertEqual('ssh://dani@github.com/conan-io/conan.git',
                         scm.get_url_with_credentials("ssh://github.com/conan-io/conan.git"))
        self.assertEqual(1, len(output.out))
        self.assertIn("WARN: SCM password cannot be set for ssh url, ignoring parameter", output.out)

    def test_ssh_username(self):
        scm = SCMBase(username="dani")
        self.assertEqual('ssh://dani@github.com/conan-io/conan.git',
                         scm.get_url_with_credentials("ssh://github.com/conan-io/conan.git"))

    def test_ssh_password(self):
        output = OutputMock()
        scm = SCMBase(password="pass", output=output)
        self.assertEqual('ssh://github.com/conan-io/conan.git',
                         scm.get_url_with_credentials("ssh://github.com/conan-io/conan.git"))
        self.assertEqual(1, len(output.out))
        self.assertIn("WARN: SCM password cannot be set for ssh url, ignoring parameter", output.out)

    def test_ssh_url_with_username_only_password(self):
        output = OutputMock()
        scm = SCMBase(password="pass", output=output)
        self.assertEqual('ssh://dani@github.com/conan-io/conan.git',
                         scm.get_url_with_credentials("ssh://dani@github.com/conan-io/conan.git"))
        self.assertEqual(1, len(output.out))
        self.assertIn("WARN: SCM password cannot be set for ssh url, ignoring parameter", output.out)

    def test_ssh_url_with_username_only_username(self):
        output = OutputMock()
        scm = SCMBase(username="dani", output=output)
        self.assertEqual('ssh://git@github.com/conan-io/conan.git',
                         scm.get_url_with_credentials("ssh://git@github.com/conan-io/conan.git"))
        self.assertIn("WARN: SCM username got from URL, ignoring 'username' parameter", output.out)

    def test_ssh_url_with_username_and_username_password(self):
        output = OutputMock()
        scm = SCMBase(password="pass", username="dani", output=output)
        self.assertEqual('ssh://git@github.com/conan-io/conan.git',
                         scm.get_url_with_credentials("ssh://git@github.com/conan-io/conan.git"))
        self.assertEqual(2, len(output.out))
        self.assertIn("WARN: SCM password cannot be set for ssh url, ignoring parameter", output.out)
        self.assertIn("WARN: SCM username got from URL, ignoring 'username' parameter", output.out)

    def test_ssh_url_with_username_password_and_only_password(self):
        output = OutputMock()
        scm = SCMBase(password="password", output=output)
        self.assertEqual('ssh://git@github.com/conan-io/conan.git',
                         scm.get_url_with_credentials("ssh://git:pass@github.com/conan-io/conan.git"))
        self.assertEqual(2, len(output.out))
        self.assertIn("WARN: SCM password cannot be set for ssh url, ignoring parameter", output.out)
        self.assertIn("WARN: Password in URL cannot be set for 'ssh' SCM type, removing it",
                      output.out)

    def test_ssh_url_with_username_password_and_only_username(self):
        output = OutputMock()
        scm = SCMBase(username="dani", output=output)
        self.assertEqual('ssh://git@github.com/conan-io/conan.git',
                         scm.get_url_with_credentials("ssh://git:pass@github.com/conan-io/conan.git"))
        self.assertEqual(2, len(output.out))
        self.assertIn("WARN: SCM username got from URL, ignoring 'username' parameter", output.out)
        self.assertIn("WARN: Password in URL cannot be set for 'ssh' SCM type, removing it",
                      output.out)

    def test_ssh_url_with_username_password_and_username_password(self):
        output = OutputMock()
        scm = SCMBase(password="password", username="dani", output=output)
        self.assertEqual("ssh://git@github.com/conan-io/conan.git",
                         scm.get_url_with_credentials("ssh://git:pass@github.com/conan-io/conan.git"))
        self.assertEqual(3, len(output.out))
        self.assertIn("WARN: SCM password cannot be set for ssh url, ignoring parameter", output.out)
        self.assertIn("WARN: SCM username got from URL, ignoring 'username' parameter", output.out)
        self.assertIn("WARN: Password in URL cannot be set for 'ssh' SCM type, removing it",
                      output.out)

    def test_scp(self):
        scm = SCMBase()
        self.assertEqual('git@github.com/conan-io/conan.git',
                         scm.get_url_with_credentials("git@github.com/conan-io/conan.git"))

    def test_scp_only_password(self):
        output = OutputMock()
        scm = SCMBase(password="pass", output=output)
        self.assertEqual("git@github.com:conan-io/conan.git",
                         scm.get_url_with_credentials("git@github.com:conan-io/conan.git"))
        self.assertIn("WARN: SCM password cannot be set for scp url, ignoring parameter", output.out)

    def test_scp_only_username(self):
        output = OutputMock()
        scm = SCMBase(username="dani", output=output)
        self.assertEqual('git@github.com:conan-io/conan.git',
                         scm.get_url_with_credentials("git@github.com:conan-io/conan.git"))
        self.assertIn("WARN: SCM username got from URL, ignoring 'username' parameter", output.out)

    def test_scp_username_password(self):
        output = OutputMock()
        scm = SCMBase(password="pass", username="dani", output=output)
        self.assertEqual("git@github.com:conan-io/conan.git",
                         scm.get_url_with_credentials("git@github.com:conan-io/conan.git"))
        self.assertEqual(2, len(output.out))
        self.assertIn("WARN: SCM password cannot be set for scp url, ignoring parameter", output.out)
        self.assertIn("WARN: SCM username got from URL, ignoring 'username' parameter", output.out)

    def test_scp_url_username_password(self):
        output = OutputMock()
        scm = SCMBase(password="password", output=output)
        self.assertEqual('git:pass@github.com:conan-io/conan.git',
                         scm.get_url_with_credentials("git:pass@github.com:conan-io/conan.git"))
        self.assertIn("WARN: URL type not supported, ignoring 'username' and 'password' "
                      "parameters", output.out)

    def test_file_url(self):
        scm = SCMBase()
        self.assertEqual("file://path/to/.git", scm.get_url_with_credentials("file://path/to/.git"))

    def test_file_url_with_username_password_params(self):
        output = OutputMock()
        scm = SCMBase(username="user", password="pass", output=output)
        self.assertEqual('file://path/to/.git', scm.get_url_with_credentials("file://path/to/.git"))
        self.assertEqual(2, len(output.out))
        self.assertIn("WARN: SCM username cannot be set for file url, ignoring parameter",
                      output.out)
        self.assertIn("WARN: SCM password cannot be set for file url, ignoring parameter",
                      output.out)

    def test_git(self):
        scm = SCMBase()
        self.assertEqual('git://github.com/conan-io/conan.git',
                         scm.get_url_with_credentials("git://github.com/conan-io/conan.git"))

    def test_git_only_password(self):
        output = OutputMock()
        scm = SCMBase(password="pass", output=output)
        self.assertEqual("git://github.com/conan-io/conan.git",
                         scm.get_url_with_credentials("git://github.com/conan-io/conan.git"))
        self.assertIn("WARN: SCM password cannot be set for git url, ignoring parameter", output.out)

    def test_git_only_username(self):
        output = OutputMock()
        scm = SCMBase(username="dani", output=output)
        self.assertEqual("git://github.com/conan-io/conan.git",
                         scm.get_url_with_credentials("git://github.com/conan-io/conan.git"))
        self.assertIn("WARN: SCM username cannot be set for git url, ignoring parameter", output.out)

    def test_git_username_password(self):
        output = OutputMock()
        scm = SCMBase(password="pass", username="dani", output=output)
        self.assertEqual("git://github.com/conan-io/conan.git",
                         scm.get_url_with_credentials("git://github.com/conan-io/conan.git"))
        self.assertEqual(2, len(output.out))
        self.assertIn("WARN: SCM password cannot be set for git url, ignoring parameter", output.out)
        self.assertIn("WARN: SCM password cannot be set for git url, ignoring parameter", output.out)

    def test_git_url_username_password(self):
        output = OutputMock()
        scm = SCMBase(password="pass", output=output)
        self.assertEqual("git://github.com/conan-io/conan.git",
                         scm.get_url_with_credentials(
                             "git://user:pass@github.com/conan-io/conan.git"))
        self.assertEqual(2, len(output.out))
        self.assertIn("WARN: SCM password cannot be set for git url, ignoring parameter", output.out)
        self.assertIn("WARN: Username/Password in URL cannot be set for 'git' SCM type, removing it",
                      output.out)
