import os
import platform
import re
import xml.etree.ElementTree as ET
from subprocess import CalledProcessError

from six.moves.urllib.parse import quote_plus, unquote, urlparse

from conans.client.tools.env import environment_append, no_op
from conans.client.tools.files import chdir
from conans.errors import ConanException
from conans.model.version import Version
from conans.util.files import decode_text, to_file_bytes, walk, mkdir
from conans.util.runners import check_output_runner, version_runner, muted_runner, input_runner, \
    pyinstaller_bundle_env_cleaned


def _check_repo(cmd, folder):
    msg = "Not a valid '{0}' repository or '{0}' not found.".format(cmd[0])
    try:
        ret = muted_runner(cmd, folder=folder)
    except Exception:
        raise ConanException(msg)
    else:
        if bool(ret):
            raise ConanException(msg)


class SCMBase(object):
    cmd_command = None

    @classmethod
    def get_version(cls):
        try:
            out = version_runner([cls.cmd_command, "--version"])
            version_line = decode_text(out).split('\n', 1)[0]
            version_str = version_line.split(' ', 3)[2]
            return Version(version_str)
        except Exception as e:
            raise ConanException("Error retrieving {} version: '{}'".format(cls.cmd_command, e))

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
                with pyinstaller_bundle_env_cleaned():
                    if not self._runner:
                        return check_output_runner(command).strip()
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
        if parsed.username and parsed.scheme == "ssh":
            netloc = "{}@{}".format(parsed.username, netloc)
        replaced = parsed._replace(netloc=netloc)
        return replaced.geturl()


class Git(SCMBase):
    cmd_command = "git"

    @property
    def _configure_ssl_verify(self):
        return "-c http.sslVerify=%s " % ("true" if self._verify_ssl else "false")

    def run(self, command):
        command = self._configure_ssl_verify + command
        return super(Git, self).run(command)

    def _fetch(self, url, branch, shallow):
        if not branch:
            raise ConanException("The destination folder '%s' is not empty, "
                                 "specify a branch to checkout (not a tag or commit) "
                                 "or specify a 'subfolder' "
                                 "attribute in the 'scm'" % self.folder)

        output = self.run("init")
        output += self.run('remote add origin "%s"' % url)
        if shallow:
            output += self.run('fetch --depth 1 origin "%s"' % branch)
            output += self.run('checkout FETCH_HEAD')
        else:
            output += self.run("fetch")
            output += self.run("checkout -t origin/%s" % branch)
        return output

    def clone(self, url, branch=None, args="", shallow=False):
        """
        :param url: repository remote URL to clone from (e.g. https, git or local)
        :param branch: actually, can be any valid git ref expression like,
        - None, use default branch, usually it's "master"
        - branch name
        - tag name
        - revision sha256
        - expression like HEAD~1
        :param args: additional arguments to be passed to the git command (e.g. config args)
        :param shallow:
        :return: output of the clone command
        """
        # TODO: rename "branch" -> "element" in Conan 2.0
        url = self.get_url_with_credentials(url)
        if os.path.exists(url):
            url = url.replace("\\", "/")  # Windows local directory
        mkdir(self.folder)  # might not exist in case of shallow clone
        if os.listdir(self.folder):
            return self._fetch(url, branch, shallow)
        if shallow and branch:
            return self._fetch(url, branch, shallow)
        branch_cmd = "--branch %s" % branch if branch else ""
        shallow_cmd = "--depth 1" if shallow else ""
        output = self.run('clone "%s" . %s %s %s' % (url, branch_cmd, shallow_cmd, args))

        return output

    def checkout(self, element, submodule=None):
        # Element can be a tag, branch or commit
        self.check_repo()
        output = self.run('checkout "%s"' % element)
        output += self.checkout_submodules(submodule)

        return output

    def checkout_submodules(self, submodule=None):
        """Do the checkout only for submodules"""
        if not submodule:
            return ""
        if submodule == "shallow":
            output = self.run("submodule sync")
            output += self.run("submodule update --init")
            return output
        elif submodule == "recursive":
            output = self.run("submodule sync --recursive")
            output += self.run("submodule update --init --recursive")
            return output
        else:
            raise ConanException("Invalid 'submodule' attribute value in the 'scm'. "
                                 "Unknown value '%s'. Allowed values: ['shallow', 'recursive']"
                                 % submodule)

    def excluded_files(self):
        ret = []
        try:
            file_paths = [os.path.normpath(
                                os.path.join(
                                    os.path.relpath(folder, self.folder), el)).replace("\\", "/")
                          for folder, dirpaths, fs in walk(self.folder)
                          for el in fs + dirpaths]
            if file_paths:
                paths = to_file_bytes("\n".join(file_paths))
                out = input_runner(['git', 'check-ignore', '--stdin'], paths, self.folder)
                grep_stdout = decode_text(out)
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
                if os.path.exists(url):  # Windows local directory
                    url = url.replace("\\", "/")
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

    def get_commit_message(self):
        self.check_repo()
        try:
            message = self.run("log -1 --format=%s%n%b")
            return message.strip()
        except Exception:
            return None

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
            return check_output_runner(command)
        runner = runner or runner_no_strip
        super(SVN, self).__init__(folder=folder, runner=runner, *args, **kwargs)

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
        if self._username and self._password:
            extra_options += " --username=" + self._username
            extra_options += " --password=" + self._password
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
        revision = self.get_revision()
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
            except CalledProcessError:
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

    def get_revision_message(self):
        output = self.run("log -r COMMITTED").splitlines()
        return output[3] if len(output) > 2 else None

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
