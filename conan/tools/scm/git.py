import os

from conan.tools.files import chdir
from conans.errors import ConanException
from conans.util.files import mkdir
from conans.util.runners import check_output_runner


class Git(object):
    def __init__(self, conanfile, folder):
        self._conanfile = conanfile
        self.folder = folder

    def _run(self, cmd):
        with chdir(self._conanfile, self.folder):
            return check_output_runner("git {}".format(cmd)).strip()

    def get_commit(self):
        try:
            commit = self._run("rev-parse HEAD")
            return commit
        except Exception as e:
            raise ConanException("Unable to get git commit in '%s': %s" % (self.folder, str(e)))

    def get_remote_url(self, remote="origin"):
        remotes = self._run("remote -v")
        for r in remotes.splitlines():
            name, url = r.split(maxsplit=1)
            if name == remote:
                url, _ = url.rsplit(None, 1)
                if os.path.exists(url):  # Windows local directory
                    url = url.replace("\\", "/")
                return url

    def commit_in_remote(self, commit, remote="origin", branch="master"):
        if not remote or not branch:
            return False
        try:
            branches = self._run("branch -r --contains {}".format(commit))
            return "{}/{}".format(remote, branch) in branches
        except Exception as e:
            raise ConanException("Unable to check remote commit in '%s': %s" % (self.folder, str(e)))

    def is_dirty(self):
        status = self._run("status -s").strip()
        return bool(status)

    def get_url_commit(self, remote="origin", branch="master"):
        dirty = self.is_dirty()
        if dirty:
            raise ConanException("Repo is dirty, cannot capture url and commit: "
                                 "{}".format(self.folder))
        commit = self.get_commit()
        url = self.get_remote_url(remote=remote)
        in_remote = self.commit_in_remote(commit, remote=remote, branch=branch)
        if in_remote:
            return url, commit
        return self.folder, commit

    def clone(self, url, target=""):
        if os.path.exists(url):
            url = url.replace("\\", "/")  # Windows local directory
        mkdir(self.folder)
        self._run('clone "{}" {}'.format(url, target))
