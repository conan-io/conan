import os

import re
import subprocess
from six.moves.urllib.parse import urlparse, quote_plus
from subprocess import CalledProcessError, PIPE, STDOUT

from conans.client.tools.env import no_op, environment_append
from conans.client.tools.files import chdir
from conans.errors import ConanException
from conans.util.files import decode_text, to_file_bytes


class Git(object):

    def __init__(self, folder=None, verify_ssl=True, username=None, password=None,
                 force_english=True, runner=None):
        self.folder = folder or os.getcwd()
        if not os.path.exists(self.folder):
            os.makedirs(self.folder)
        self._verify_ssl = verify_ssl
        self._force_eng = force_english
        self._username = username
        self._password = password
        self._runner = runner

    def run(self, command):
        command = "git %s" % command
        with chdir(self.folder) if self.folder else no_op():
            with environment_append({"LC_ALL": "en_US.UTF-8"}) if self._force_eng else no_op():
                if not self._runner:
                    return subprocess.check_output(command, shell=True).decode().strip()
                else:
                    return self._runner(command)

    def get_repo_root(self):
        return self.run("rev-parse --show-toplevel")

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
        if os.path.exists(url):
            url = url.replace("\\", "/")  # Windows local directory
        if os.path.exists(self.folder) and os.listdir(self.folder):
            if not branch:
                raise ConanException("The destination folder '%s' is not empty, "
                                     "specify a branch to checkout (not a tag or commit) "
                                     "or specify a 'subfolder' "
                                     "attribute in the 'scm'" % self.folder)
            output = self.run("init")
            output += self._configure_ssl_verify()
            output += self.run('remote add origin "%s"' % url)
            output += self.run("fetch ")
            output += self.run("checkout -t origin/%s" % branch)
        else:
            branch_cmd = "--branch %s" % branch if branch else ""
            output = self.run('clone "%s" . %s' % (url, branch_cmd))
            output += self._configure_ssl_verify()

        return output

    def checkout(self, element, submodule=None):
        self._check_git_repo()
        output = self.run('checkout "%s"' % element)

        if submodule:
            if submodule == "shallow":
                output += self.run("submodule sync")
                output += self.run("submodule update --init")
            elif submodule == "recursive":
                output += self.run("submodule sync --recursive")
                output += self.run("submodule update --init --recursive")
            else:
                raise ConanException("Invalid 'submodule' attribute value in the 'scm'. "
                                     "Unknown value '%s'. Allowed values: ['shallow', 'recursive']" % submodule)
        # Element can be a tag, branch or commit
        return output

    def excluded_files(self):
        try:

            file_paths = [os.path.normpath(os.path.join(os.path.relpath(folder, self.folder), el)).replace("\\", "/")
                          for folder, dirpaths, fs in os.walk(self.folder)
                          for el in fs + dirpaths]
            p = subprocess.Popen(['git', 'check-ignore', '--stdin'],
                                 stdout=PIPE, stdin=PIPE, stderr=STDOUT, cwd=self.folder)
            paths = to_file_bytes("\n".join(file_paths))
            grep_stdout = decode_text(p.communicate(input=paths)[0])
            tmp = grep_stdout.splitlines()
        except CalledProcessError:
            tmp = []
        return tmp

    def get_remote_url(self, remote_name=None):
        self._check_git_repo()
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

    def get_commit(self):
        self._check_git_repo()
        try:
            commit = self.run("rev-parse HEAD")
            commit = commit.strip()
            return commit
        except Exception as e:
            raise ConanException("Unable to get git commit from %s\n%s" % (self.folder, str(e)))

    get_revision = get_commit

    def _check_git_repo(self):
        try:
            self.run("status")
        except Exception:
            raise ConanException("Not a valid git repository")

    def get_branch(self):
        self._check_git_repo()
        try:
            status = self.run("status -bs --porcelain")
            # ## feature/scm_branch...myorigin/feature/scm_branch
            branch = status.splitlines()[0].split("...")[0].strip("#").strip()
            return branch
        except Exception as e:
            raise ConanException("Unable to get git branch from %s\n%s" % (self.folder, str(e)))
