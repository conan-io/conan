
import os
import sys
import re

import subprocess
from six.moves.urllib.parse import urlparse, quote_plus, unquote
from subprocess import CalledProcessError, PIPE, STDOUT
import platform

from conans.client.tools.env import no_op, environment_append
from conans.client.tools.files import chdir
from conans.errors import ConanException
from conans.model.version import Version
from conans.util.files import decode_text, to_file_bytes, walk


class SCMBase(object):
    cmd_command = None

    def __init__(self, folder=None, verify_ssl=True, username=None, password=None, force_english=True,
                 runner=None):
        self.folder = folder or os.getcwd()
        if not os.path.exists(self.folder):
            os.makedirs(self.folder)
        self._verify_ssl = verify_ssl
        self._force_eng = force_english
        self._username = username
        self._password = password
        self._runner = runner

    def run(self, command):
        command = "%s %s" % (self.cmd_command, command)
        with chdir(self.folder) if self.folder else no_op():
            with environment_append({"LC_ALL": "en_US.UTF-8"}) if self._force_eng else no_op():
                if not self._runner:
                    return decode_text(subprocess.check_output(command, shell=True).strip())
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


class Git(SCMBase):
    cmd_command = "git"

    def _configure_ssl_verify(self):
        # TODO: This should be a context manager
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
                          for folder, dirpaths, fs in walk(self.folder)
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
        remotes = self.run("remote -v")
        for remote in remotes.splitlines():
            name, url = remote.split(None, 1)
            if name == remote_name:
                url, _ = url.rsplit(None, 1)
                return url
        return None

    def is_local_repository(self):
        url = self.get_remote_url()
        return os.path.exists(url)   

    def get_commit(self):
        self._check_git_repo()
        try:
            commit = self.run("rev-parse HEAD")
            commit = commit.strip()
            return commit
        except Exception as e:
            raise ConanException("Unable to get git commit from '%s': %s" % (self.folder, str(e)))

    get_revision = get_commit

    def is_pristine(self):
        self._check_git_repo()
        status = self.run("status --porcelain").strip()
        if not status:
            return True
        else:
            return False
        
    def get_repo_root(self):
        self._check_git_repo()
        return self.run("rev-parse --show-toplevel")

    def get_branch(self):
        self._check_git_repo()
        try:
            status = self.run("status -bs --porcelain")
            # ## feature/scm_branch...myorigin/feature/scm_branch
            branch = status.splitlines()[0].split("...")[0].strip("#").strip()
            return branch
        except Exception as e:
            raise ConanException("Unable to get git branch from %s: %s" % (self.folder, str(e)))

    def _check_git_repo(self):
        try:
            self.run("status")
        except Exception:
            raise ConanException("Not a valid git repository")


class SVN(SCMBase):
    cmd_command = "svn"
    file_protocol = 'file:///' if platform.system() == "Windows" else 'file://'
    API_CHANGE_VERSION = Version("1.10")  # CLI changes in 1.9.x

    def __init__(self, folder=None, runner=None, *args, **kwargs):
        def runner_no_strip(command):
            return decode_text(subprocess.check_output(command, shell=True))
        runner = runner or runner_no_strip
        super(SVN, self).__init__(folder=folder, runner=runner, *args, **kwargs)

    @staticmethod
    def get_version():
        try:
            out, err = subprocess.Popen(["svn", "--version"], stdout=subprocess.PIPE).communicate()
            version_line = decode_text(out).split('\n', 1)[0]
            version_str = version_line.split(' ', 3)[2]
            return Version(version_str)
        except Exception as e:
            raise ConanException("Error retrieving SVN version: '{}'".format(e))

    @property
    def version(self):
        if not hasattr(self, '_version'):
            version = SVN.get_version()
            setattr(self, '_version', version)
        return getattr(self, '_version')

    def run(self, command):
        # Ensure we always pass some params
        extra_options = " --no-auth-cache --non-interactive"
        if not self._verify_ssl:
            if self.version >= SVN.API_CHANGE_VERSION:
                extra_options += " --trust-server-cert-failures=unknown-ca"
            else:
                extra_options += " --trust-server-cert"
        return super(SVN, self).run(command="{} {}".format(command, extra_options))

    def checkout(self, url, revision="HEAD"):
        output = ""
        try:
            self._check_svn_repo()
        except ConanException:
            output += self.run('co "{url}" .'.format(url=url))
        else:
            assert url.lower() == self.get_remote_url().lower(), \
                "%s != %s" % (url, self.get_remote_url())
            output += self.run("revert . --recursive")
        finally:
            output += self.update(revision=revision)
        return output

    def update(self, revision='HEAD'):
        self._check_svn_repo()
        return self.run("update -r {rev}".format(rev=revision))

    def excluded_files(self):
        self._check_svn_repo()
        excluded_list = []
        output = self.run("status --no-ignore")
        for it in output.splitlines():
            if it[0] == 'I':  # Only ignored files
                filepath = it[8:].strip()
                excluded_list.append(os.path.normpath(filepath))
        return excluded_list

    def get_remote_url(self):
        return self.run("info --show-item url").strip()

    def get_qualified_remote_url(self):
        # Return url with peg revision
        url = self.get_remote_url()
        revision = self.get_last_changed_revision()
        return "{url}@{revision}".format(url=url, revision=revision)
        
    def is_local_repository(self):
        url = self.get_remote_url()
        return url.startswith(self.file_protocol) and \
               os.path.exists(unquote(url[len(self.file_protocol):]))

    def is_pristine(self):
        # Check if working copy is pristine/consistent
        output = self.run("status -u -r {}".format(self.get_revision()))
        offending_columns = [0, 1, 2, 3, 4, 6, 7, 8]  # 5th column informs if the file is locked (7th is always blank)

        for item in output.splitlines()[:-1]:
            if item[0] == '?':  # Untracked file
                continue
            if any(item[i] != ' ' for i in offending_columns):
                return False

        return True

    def get_revision(self):
        return self.run("info --show-item revision").strip()

    def get_repo_root(self):
        return self.run("info --show-item wc-root").strip()

    def get_last_changed_revision(self, use_wc_root=True):
        if use_wc_root:
            return self.run('info "{root}" --show-item last-changed-revision'.format(
                root=self.get_repo_root())).strip()
        else:
            return self.run("info --show-item last-changed-revision").strip()

    def get_branch(self):
        url = self.run("info --show-item relative-url").strip()
        try:
            pattern = "(tags|branches)/[^/]+|trunk"
            branch = re.search(pattern, url)
            
            if branch is None:
                return None
            else:
                return branch.group(0)
        except Exception as e:
            raise ConanException("Unable to get svn branch from %s: %s" % (self.folder, str(e)))

    def _check_svn_repo(self):
        try:
            self.run("info")
        except Exception:
            raise ConanException("Not a valid SVN repository")