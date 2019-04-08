import os
import platform
import re
import subprocess
import xml.etree.ElementTree as ET
from subprocess import CalledProcessError, PIPE, STDOUT

from six.moves.urllib.parse import quote_plus, unquote, urlparse

from conans.client.tools import check_output
from conans.client.tools.env import environment_append, no_op
from conans.client.tools.files import chdir
from conans.errors import ConanException
from conans.model.version import Version
from conans.util.files import decode_text, to_file_bytes, walk


def _run_muted(cmd, folder=None):
    with chdir(folder) if folder else no_op():
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        process.communicate()
        return process.returncode


def _check_repo(cmd, folder, msg=None):
    msg = msg or "Not a valid '{}' repository".format(cmd[0])
    try:
        ret = _run_muted(cmd, folder=folder)
    except Exception:
        raise ConanException(msg)
    else:
        if bool(ret):
            raise ConanException(msg)


class SCMBase(object):
    cmd_command = None

    def __init__(self, folder=None, verify_ssl=True, username=None, password=None,
                 force_english=True, runner=None, output=None):
        self.folder = folder or os.getcwd()
        if not os.path.exists(self.folder):
            os.makedirs(self.folder)
        self._verify_ssl = verify_ssl
        self._force_eng = force_english
        self._username = username
        self._password = password
        self._runner = runner
        self._output = output

    def run(self, command):
        command = "%s %s" % (self.cmd_command, command)
        with chdir(self.folder) if self.folder else no_op():
            with environment_append({"LC_ALL": "en_US.UTF-8"}) if self._force_eng else no_op():
                if not self._runner:
                    return check_output(command).strip()
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

    @classmethod
    def _remove_credentials_url(cls, url):
        parsed = urlparse(url)
        netloc = parsed.hostname
        if parsed.port:
            netloc += ":{}".format(parsed.port)
        replaced = parsed._replace(netloc=netloc)
        return replaced.geturl()


class Git(SCMBase):
    cmd_command = "git"

    def _configure_ssl_verify(self):
        # TODO: This should be a context manager
        return self.run("config http.sslVerify %s" % ("true" if self._verify_ssl else "false"))

    def clone(self, url, branch=None, args=""):
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
            output = self.run('clone "%s" . %s %s' % (url, branch_cmd, args))
            output += self._configure_ssl_verify()

        return output

    def checkout(self, element, submodule=None):
        self.check_repo()
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
                                     "Unknown value '%s'. Allowed values: ['shallow', 'recursive']"
                                     % submodule)
        # Element can be a tag, branch or commit
        return output

    def excluded_files(self):
        ret = []
        try:
            file_paths = [os.path.normpath(
                                os.path.join(
                                    os.path.relpath(folder, self.folder), el)).replace("\\", "/")
                          for folder, dirpaths, fs in walk(self.folder)
                          for el in fs + dirpaths]
            if file_paths:
                p = subprocess.Popen(['git', 'check-ignore', '--stdin'],
                                     stdout=PIPE, stdin=PIPE, stderr=STDOUT, cwd=self.folder)
                paths = to_file_bytes("\n".join(file_paths))

                grep_stdout = decode_text(p.communicate(input=paths)[0])
                ret = grep_stdout.splitlines()
        except (CalledProcessError, IOError, OSError) as e:
            if self._output:
                self._output.warn("Error checking excluded git files: %s. "
                                  "Ignoring excluded files" % e)
            ret = []
        return ret

    def get_remote_url(self, remote_name=None, remove_credentials=False):
        self.check_repo()
        remote_name = remote_name or "origin"
        remotes = self.run("remote -v")
        for remote in remotes.splitlines():
            name, url = remote.split(None, 1)
            if name == remote_name:
                url, _ = url.rsplit(None, 1)
                if remove_credentials and not os.path.exists(url):  # only if not local
                    url = self._remove_credentials_url(url)
                return url
        return None

    def is_local_repository(self):
        url = self.get_remote_url()
        return os.path.exists(url)

    def get_commit(self):
        self.check_repo()
        try:
            commit = self.run("rev-parse HEAD")
            commit = commit.strip()
            return commit
        except Exception as e:
            raise ConanException("Unable to get git commit from '%s': %s" % (self.folder, str(e)))

    get_revision = get_commit

    def is_pristine(self):
        self.check_repo()
        status = self.run("status --porcelain").strip()
        if not status:
            return True
        else:
            return False

    def get_repo_root(self):
        self.check_repo()
        return self.run("rev-parse --show-toplevel")

    def get_branch(self):
        self.check_repo()
        try:
            status = self.run("status -bs --porcelain")
            # ## feature/scm_branch...myorigin/feature/scm_branch
            branch = status.splitlines()[0].split("...")[0].strip("#").strip()
            return branch
        except Exception as e:
            raise ConanException("Unable to get git branch from %s: %s" % (self.folder, str(e)))

    def get_tag(self):
        self.check_repo()
        try:
            status = self.run("describe --exact-match --tags")
            tag = status.strip()
            return tag
        except Exception:
            return None

    def check_repo(self):
        """ Check if it is a valid GIT repo """
        _check_repo(["git", "status"], folder=self.folder)


class SVN(SCMBase):
    cmd_command = "svn"
    file_protocol = 'file:///' if platform.system() == "Windows" else 'file://'
    API_CHANGE_VERSION = Version("1.9")  # CLI changes in 1.9

    def __init__(self, folder=None, runner=None, *args, **kwargs):
        def runner_no_strip(command):
            return decode_text(subprocess.check_output(command, shell=True))
        runner = runner or runner_no_strip
        super(SVN, self).__init__(folder=folder, runner=runner, *args, **kwargs)

    @staticmethod
    def get_version():
        try:
            out, _ = subprocess.Popen(["svn", "--version"], stdout=subprocess.PIPE).communicate()
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

    def _show_item(self, item, target='.'):
        self.check_repo()
        if self.version >= SVN.API_CHANGE_VERSION:
            value = self.run("info --show-item {item} \"{target}\"".format(item=item, target=target))
            return value.strip()
        else:
            output = self.run("info --xml \"{target}\"".format(target=target))
            root = ET.fromstring(output)
            if item == 'revision':
                return root.findall("./entry")[0].get("revision")
            elif item == 'url':
                return root.findall("./entry/url")[0].text
            elif item == 'wc-root':
                return root.findall("./entry/wc-info/wcroot-abspath")[0].text
            elif item == 'last-changed-revision':
                return root.findall("./entry/commit")[0].get("revision")
            elif item == 'relative-url':
                root_url = root.findall("./entry/repository/root")[0].text
                url = self._show_item(item='url', target=target)
                if url.startswith(root_url):
                    return url[len(root_url):]
            raise ConanException("Retrieval of item '{}' not implemented for SVN<{}".format(
                item, SVN.API_CHANGE_VERSION))

    def checkout(self, url, revision="HEAD"):
        output = ""
        try:
            self.check_repo()
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
        self.check_repo()
        return self.run("update -r {rev}".format(rev=revision))

    def excluded_files(self):
        self.check_repo()
        excluded_list = []
        output = self.run("status --no-ignore")
        for it in output.splitlines():
            if it.startswith('I'):  # Only ignored files
                filepath = it[8:].strip()
                excluded_list.append(os.path.normpath(filepath))
        return excluded_list

    def get_remote_url(self, remove_credentials=False):
        url = self._show_item('url')
        if remove_credentials and not os.path.exists(url):  # only if not local
            url = self._remove_credentials_url(url)
        return url

    def get_qualified_remote_url(self, remove_credentials=False):
        # Return url with peg revision
        url = self.get_remote_url(remove_credentials=remove_credentials)
        revision = self.get_last_changed_revision()
        return "{url}@{revision}".format(url=url, revision=revision)

    def is_local_repository(self):
        url = self.get_remote_url()
        return (url.startswith(self.file_protocol) and
                os.path.exists(unquote(url[len(self.file_protocol):])))

    def is_pristine(self):
        # Check if working copy is pristine/consistent
        if self.version >= SVN.API_CHANGE_VERSION:
            try:
                output = self.run("status -u -r {} --xml".format(self.get_revision()))
            except subprocess.CalledProcessError:
                return False
            else:
                root = ET.fromstring(output)

                pristine_item_list = ['external', 'ignored', 'none', 'normal']
                pristine_props_list = ['normal', 'none']
                for item in root.findall('.//wc-status'):
                    if item.get('item', 'none') not in pristine_item_list:
                        return False
                    if item.get('props', 'none') not in pristine_props_list:
                        return False

                for item in root.findall('.//repos-status'):
                    if item.get('item', 'none') not in pristine_item_list:
                        return False
                    if item.get('props', 'none') not in pristine_props_list:
                        return False
                return True
        else:
            if self._output:
                self._output.warn("SVN::is_pristine for SVN v{} (less than {}) is not implemented,"
                                  " it is returning not-pristine always because it cannot compare"
                                  " with checked out version.".format(self.version,
                                                                      SVN.API_CHANGE_VERSION))
            return False

    def get_revision(self):
        return self._show_item('revision')

    def get_repo_root(self):
        return self._show_item('wc-root')

    def get_last_changed_revision(self, use_wc_root=True):
        if use_wc_root:
            return self._show_item(item='last-changed-revision', target=self.get_repo_root())
        else:
            return self._show_item(item='last-changed-revision')

    def get_branch(self):
        item = self._get_item("branches/[^/]+|trunk", "branch")
        return item.replace("branches/", "") if item else None

    def get_tag(self):
        item = self._get_item("tags/[^/]+", "tag")
        return item.replace("tags/", "") if item else None

    def _get_item(self, pattern, item_name):
        try:
            url = self._show_item('relative-url')
        except Exception as e:
            raise ConanException("Unable to get svn %s from %s: %s"
                                 % (item_name, self.folder, str(e)))
        item = re.search(pattern, url)
        return item.group(0) if item else None

    def check_repo(self):
        """ Check if it is a valid SVN repo """
        _check_repo(["svn", "info"], folder=self.folder)
