import os

from conan.tools.files import chdir
from conans.errors import ConanException
from conans.util.files import mkdir
from conans.util.runners import check_output_runner


class Git(object):
    """
    Git is a wrapper for several common patterns used with *git* tool.
    """
    def __init__(self, conanfile, folder="."):
        """
        :param conanfile: Conanfile instance.
        :param folder: Current directory, by default ``.``, the current working directory.
        """
        self._conanfile = conanfile
        self.folder = folder

    def run(self, cmd):
        """
        Executes ``git <cmd>``

        :return: The console output of the command.
        """
        with chdir(self._conanfile, self.folder):
            return check_output_runner("git {}".format(cmd)).strip()

    def get_commit(self):
        """
        :return: The current commit, with ``git rev-list HEAD -n 1 -- <folder>``.
            The latest commit is returned, irrespective of local not committed changes.
        """
        try:
            # commit = self.run("rev-parse HEAD") For the whole repo
            # This rev-list knows to capture the last commit for the folder
            # --full-history is needed to not avoid wrong commits:
            # https://github.com/conan-io/conan/issues/10971
            # https://git-scm.com/docs/git-rev-list#Documentation/git-rev-list.txt-Defaultmode
            commit = self.run('rev-list HEAD -n 1 --full-history -- "."')
            return commit
        except Exception as e:
            raise ConanException("Unable to get git commit in '%s': %s" % (self.folder, str(e)))

    def get_remote_url(self, remote="origin"):
        """
        Obtains the URL of the remote git remote repository, with ``git remote -v``

        **Warning!**
        Be aware that This method will get the output from ``git remote -v``.
        If you added tokens or credentials to the remote in the URL, they will be exposed.
        Credentials shouldn’t be added to git remotes definitions, but using a credentials manager
        or similar mechanism. If you still want to use this approach, it is your responsibility
        to strip the credentials from the result.

        :param remote: Name of the remote git repository ('origin' by default).
        :return: URL of the remote git remote repository.
        """
        remotes = self.run("remote -v")
        for r in remotes.splitlines():
            name, url = r.split(maxsplit=1)
            if name == remote:
                url, _ = url.rsplit(None, 1)
                if os.path.exists(url):  # Windows local directory
                    url = url.replace("\\", "/")
                return url

    def commit_in_remote(self, commit, remote="origin"):
        """
        Checks that the given commit exists in the remote, with ``branch -r --contains <commit>``
        and checking an occurrence of a branch in that remote exists.

        :param commit: Commit to check.
        :param remote: Name of the remote git repository ('origin' by default).
        :return: True if the given commit exists in the remote, False otherwise.
        """
        if not remote:
            return False
        try:
            branches = self.run("branch -r --contains {}".format(commit))
            return "{}/".format(remote) in branches
        except Exception as e:
            raise ConanException("Unable to check remote commit in '%s': %s" % (self.folder, str(e)))

    def is_dirty(self):
        """
        Returns if the current folder is dirty, running ``git status -s``

        :return: True, if the current folder is dirty. Otherwise, False.
        """
        status = self.run("status -s").strip()
        return bool(status)

    def get_url_and_commit(self, remote="origin"):
        """
        This is an advanced method, that returns both the current commit, and the remote repository url.
        This method is intended to capture the current remote coordinates for a package creation,
        so that can be used later to build again from sources from the same commit. This is the behavior:

        * If the repository is dirty, it will raise an exception. Doesn’t make sense to capture coordinates
          of something dirty, as it will not be reproducible. If there are local changes, and the
          user wants to test a local conan create, should commit the changes first (locally, not push the changes).

        * If the repository is not dirty, but the commit doesn’t exist in the given remote, the method
          will return that commit and the URL of the local user checkout. This way, a package can be
          conan create created locally, testing everything works, before pushing some changes to the remote.

        * If the repository is not dirty, and the commit exists in the specified remote, it will
          return that commit and the url of the remote.

        **Warning!**
        Be aware that This method will get the output from ``git remote -v``.
        If you added tokens or credentials to the remote in the URL, they will be exposed.
        Credentials shouldn’t be added to git remotes definitions, but using a credentials manager
        or similar mechanism. If you still want to use this approach, it is your responsibility
        to strip the credentials from the result.

        :param remote: Name of the remote git repository ('origin' by default).
        :return: (url, commit) tuple
        """
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

        self._conanfile.output.warning("Current commit {} doesn't exist in remote {}\n"
                                       "This revision will not be buildable in other "
                                       "computer".format(commit, remote))
        return self.get_repo_root(), commit

    def get_repo_root(self):
        """
        Get the current repository top folder with ``git rev-parse --show-toplevel``

        :return: Repository top folder.
        """
        folder = self.run("rev-parse --show-toplevel")
        return folder.replace("\\", "/")

    def clone(self, url, target="", args=None):
        """
        Performs a ``git clone <url> <args> <target>`` operation, where target is the target directory.

        :param url: URL of remote repository.
        :param target: Target folder.
        :param args: Extra arguments to pass to the git clone as a list.
        """
        args = args or []
        if os.path.exists(url):
            url = url.replace("\\", "/")  # Windows local directory
        mkdir(self.folder)
        self._conanfile.output.info("Cloning git repo")
        self.run('clone "{}" {} {}'.format(url, " ".join(args), target))

    def checkout(self, commit):
        """
        Checkouts the given commit using ``git checkout <commit>``.

        :param commit: Commit to checkout.
        """
        self._conanfile.output.info("Checkout: {}".format(commit))
        self.run('checkout {}'.format(commit))

    def included_files(self):
        """
        Run ``git ls-files --full-name --others --cached --exclude-standard`` to the get the list
            of files not ignored by ``.gitignore``

        :return: List of files.
        """
        files = self.run("ls-files --full-name --others --cached --exclude-standard")
        files = files.splitlines()
        return files
