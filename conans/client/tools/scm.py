import os
import platform
import subprocess

from six.moves.urllib.parse import urlparse, quote_plus

from conans.client.tools.env import no_op
from conans.client.tools.files import chdir
from conans.errors import ConanException


class Git(object):

    def __init__(self, folder, verify_ssl=True, username=None, password=None, force_english=True,
                 runner=None):
        self.folder = folder
        self._verify_ssl = verify_ssl
        self._force_english = force_english
        self._username = username
        self._password = password
        self._runner = runner

    def run(self, command):
        def english_output(cmd):
            if not self._force_english:
                return cmd
            # Git in german will be forced to output messages in english
            if platform.system() == "Windows":
                return "set LC_ALL=en_US.UTF-8 && %s" % cmd
            else:
                return "LC_ALL=en_US.UTF-8 %s" % cmd

        with chdir(self.folder) if self.folder else no_op():
            command = english_output('git %s' % command)
            if not self._runner:
                return subprocess.check_output(command, shell=True).decode().strip()
            else:
                return self._runner(command)

    def get_url_with_credentials(self, url):
        if not self._username or not self._password:
            return url
        if urlparse(url).password:
            return url

        user_enc = quote_plus(self._username)
        pwd_enc = quote_plus(self._password)
        url = url.replace("://", "://" + user_enc + ":" + pwd_enc + "@", 1)
        return url

    def _configure_ssl_verify(self):
        return self.run("config http.sslVerify %s" % ("true" if self._verify_ssl else "false"))

    def clone(self, url, branch=None):
        url = self.get_url_with_credentials(url)
        if os.path.exists(self.folder) and os.listdir(self.folder):
            if not branch:
                raise ConanException("The destination folder is not empty, "
                                     "specify a branch to checkout")
            output = self.run("init")
            output += self._configure_ssl_verify()
            output += self.run("remote add origin %s" % url)
            output += self.run("fetch ")
            output += self.run("checkout -t origin/%s" % branch)
        else:
            branch_cmd = "--branch %s" % branch if branch else ""
            output = self.run('clone "%s" . %s' % (url, branch_cmd))
            output += self._configure_ssl_verify()
        return output

    def checkout(self, element):
        # Element can be a tag, branch or commit
        return self.run('checkout "%s"' % element)

    def get_remote_url(self, remote_name=None):
        remote_name = remote_name or "origin"
        try:
            remotes = self.run("remote -v")
            for remote in remotes.splitlines():
                try:
                    name, url = remote.split(None, 1)
                    url, _ = url.rsplit(None, 1)
                    if name == remote_name:
                        return url
                except Exception:
                    pass
        except subprocess.CalledProcessError:
            pass
        return None

    def get_revision(self):
        try:
            commit = self.run("rev-parse HEAD")
            commit = commit.strip()
            return commit
        except Exception as e:
            raise ConanException("Unable to get git commit from %s\n%s" % (self.folder, str(e)))
