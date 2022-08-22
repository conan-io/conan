import os

from conan.tools.files import chdir
from conans.errors import ConanException
from conans.util.files import mkdir
from conans.util.runners import check_output_runner


class Git(object):
    def __init__(self, conanfile, folder="."):
        self._conanfile = conanfile
        self.folder = folder

    def _run(self, cmd):
        with chdir(self._conanfile, self.folder):
            return check_output_runner("git {}".format(cmd)).strip()

    def get_commit(self):
        try:
            # commit = self._run("rev-parse HEAD") For the whole repo
            # This rev-list knows to capture the last commit for the folder
            # --full-history is needed to not avoid wrong commits:
            # https://github.com/conan-io/conan/issues/10971
            # https://git-scm.com/docs/git-rev-list#Documentation/git-rev-list.txt-Defaultmode
            commit = self._run('rev-list HEAD -n 1 --full-history -- "."')
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

    def commit_in_remote(self, commit, remote="origin"):
        if not remote:
            return False
        try:
            branches = self._run("branch -r --contains {}".format(commit))
            return "{}/".format(remote) in branches
        except Exception as e:
            raise ConanException("Unable to check remote commit in '%s': %s" % (self.folder, str(e)))

    def is_dirty(self):
        status = self._run("status -s").strip()
        return bool(status)

    def get_url_and_commit(self, remote="origin"):
        dirty = self.is_dirty()
        if dirty:
            raise ConanException("Repo is dirty, cannot capture url and commit: "
                                 "{}".format(self.folder))
        commit = self.get_commit()
        url = self.get_remote_url(remote=remote)
        in_remote = self.commit_in_remote(commit, remote=remote)
        if in_remote:
            return url, commit
        # TODO: Once we know how to pass [conf] to export, enable this
        # conf_name = "tools.scm:local"
        # allow_local = self._conanfile.conf[conf_name]
        # if not allow_local:
        #    raise ConanException("Current commit {} doesn't exist in remote {}\n"
        #                         "use '-c {}=1' to allow it".format(commit, remote, conf_name))

        self._conanfile.output.warn("Current commit {} doesn't exist in remote {}\n"
                                    "This revision will not be buildable in other "
                                    "computer".format(commit, remote))
        return self.get_repo_root(), commit

    def get_repo_root(self):
        folder = self._run("rev-parse --show-toplevel")
        return folder.replace("\\", "/")

    def clone(self, url, target="", args=None):
        args = args or []
        if os.path.exists(url):
            url = url.replace("\\", "/")  # Windows local directory
        mkdir(self.folder)
        self._conanfile.output.info("Cloning git repo")
        self._run('clone "{}" {} {}'.format(url, " ".join(args), target))

    def checkout(self, commit):
        self._conanfile.output.info("Checkout: {}".format(commit))
        self._run('checkout {}'.format(commit))
