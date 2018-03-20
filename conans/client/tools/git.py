import subprocess
from conans import tools
from conans.errors import ConanException


def git_uncommitted(folder):
    with tools.chdir(folder):
        try:
            command = "git diff-index HEAD --quiet --"
            subprocess.check_output(command, shell=True)
            return False
        except subprocess.CalledProcessError:
            return True


def git_origin(folder):
    with tools.chdir(folder):
        try:
            command = "git remote -v"
            remotes = subprocess.check_output(command, shell=True).decode().strip()
            for remote in remotes.splitlines():
                try:
                    name, url = remote.split(None, 1)
                    url, _ = url.rsplit(None, 1)
                    if name == "origin":
                        return url
                except Exception:
                    pass
        except subprocess.CalledProcessError:
            pass
    return None


def git_branch(folder):
    with tools.chdir(folder):
        command = "git branch"
        try:
            branches = subprocess.check_output(command, shell=True).decode().strip()
            branches = [branch.replace("*", "").strip() for branch in branches.splitlines()
                        if branch.lstrip()[0] == "*"]
            branch = branches[0]
            return branch
        except Exception as e:
            raise ConanException("Unable to get git branch from %s\n%s" % (folder, str(e)))


def git_commit(folder):
    with tools.chdir(folder):
        command = "git rev-parse HEAD"
        try:
            commit = subprocess.check_output(command, shell=True).decode().strip()
            commit = commit.strip()
            return commit
        except Exception as e:
            raise ConanException("Unable to get git commit from %s\n%s" % (folder, str(e)))
