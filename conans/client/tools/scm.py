
import os
import sys
import re
import subprocess
from six.moves.urllib.parse import urlparse, quote_plus
from subprocess import CalledProcessError, PIPE, STDOUT

from conans.client.tools.env import no_op, environment_append
from conans.client.tools.files import chdir
from conans.errors import ConanException
from conans.util.files import decode_text, to_file_bytes
from conans.client.output import ConanOutput


class SCMBase(object):
    cmd_command = None

    def __init__(self, folder=None, verify_ssl=True, username=None, password=None, force_english=True,
                 runner=None, output=None):
        self.folder = folder or os.getcwd()
        if not os.path.exists(self.folder):
            os.makedirs(self.folder)
        self._verify_ssl = verify_ssl
        self._force_eng = force_english
        self._username = username
        self._password = password
        self._runner = runner
        self.output = output or ConanOutput(sys.stdout, True)

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

    def get_qualified_remote_url(self):
        url = self.get_remote_url()
        if os.path.exists(url):
            url = url.replace("\\", "/")
        return url

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
            raise ConanException("Unable to get git commit from %s\n%s" % (self.folder, str(e)))

    def is_pristine(self):
        return True  # TODO: To be implemented

    get_revision = get_commit

    def get_repo_root(self):
        return self.run("rev-parse --show-toplevel")

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


class SVN(SCMBase):
    cmd_command = "svn"

    def __init__(self, folder=None, runner=None, *args, **kwargs):
        def runner_no_strip(command):
            return decode_text(subprocess.check_output(command, shell=True))
        runner = runner or runner_no_strip
        super(SVN, self).__init__(folder=folder, runner=runner, *args, **kwargs)

    def run(self, command):
        # Ensure we always pass some params
        return super(SVN, self).run(command="{} --no-auth-cache --non-interactive".format(command))

    def clone(self, url, submodule=None):
        assert submodule is None, "Argument not handled"
        assert os.path.exists(self.folder), "It guaranteed to exists according to SCMBase::__init__"
        params = " --trust-server-cert-failures=unknown-ca" if not self._verify_ssl else ""

        output = ""
        if not os.path.exists(os.path.join(self.folder, '.svn')):
            url = self.get_url_with_credentials(url)
            command = 'co "{url}" . {params}'.format(url=url, params=params)
            output += self.run(command)
        output += self.run("revert . --recursive {params}".format(params=params))
        # output += self.run("cleanup . --remove-unversioned --remove-ignored {params}".format(params=params))

        return output

    def checkout(self, element, submodule=None):
        # Element can only be a revision number
        return self.run("update -r {rev}".format(rev=element))

    def excluded_files(self):
        excluded_list = []
        output = self.run("status --no-ignore")
        for it in output.splitlines():
            if it[0] == 'I':  # Only ignored files
                filepath = it[8:].strip()
                excluded_list.append(os.path.normpath(filepath))
        excluded_list.append(".svn")
        return excluded_list

    def get_remote_url(self):
        url = self.run("info --show-item url").strip()
        revision = self.run("info --show-item revision").strip()
        return "{url}@{revision}".format(url=url, revision=revision)

    def get_qualified_remote_url(self):
        url = self.run("info --show-item url").strip()
        revision = self.run("info --show-item revision").strip()
        return "{url}@{revision}".format(url=url, revision=revision)
        
    def is_local_repository(self):
        url = self.get_remote_url()
        return url.startswith("file://")   

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

    def get_last_changed_revision(self):
        return self.run("info --show-item last-changed-revision").strip()

    def get_branch(self):
        url = self.run("info --show-item relative-url").strip()
        try:
            pattern = "(tags|branches)/[^/]+|trunk"
            branch = re.search(pattern, url)
            
            if branch is None:
                return None
            else:
                return branch[0]
        except Exception as e:
            raise ConanException("Unable to get svn branch from %s\n%s" % (self.folder, str(e)))
