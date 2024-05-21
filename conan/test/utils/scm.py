import os

from conans.test.utils.test_files import temp_folder
from conans.util.files import save_files, chdir
from conans.util.runners import check_output_runner


def git_create_bare_repo(folder=None, reponame="repo.git"):
    folder = folder or temp_folder()
    cwd = os.getcwd()
    try:
        os.chdir(folder)
        check_output_runner('git init --bare {}'.format(reponame))
        return os.path.join(folder, reponame).replace("\\", "/")
    finally:
        os.chdir(cwd)


def create_local_git_repo(files=None, branch=None, submodules=None, folder=None, commits=1,
                          tags=None, origin_url=None, main_branch="master"):
    tmp = folder or temp_folder()
    if files:
        save_files(tmp, files)

    def _run(cmd, p):
        with chdir(p):
            return check_output_runner("git {}".format(cmd)).strip()

    _run("init .", tmp)
    _run('config user.name "Your Name"', tmp)
    _run('config user.email "you@example.com"', tmp)
    _run("checkout -b {}".format(branch or main_branch), tmp)

    _run("add .", tmp)
    for i in range(0, commits):
        _run('commit --allow-empty -m "commiting"', tmp)

    tags = tags or []
    for tag in tags:
        _run("tag %s" % tag, tmp)

    if submodules:
        for submodule in submodules:
            _run('submodule add "%s"' % submodule, tmp)
        _run('commit -m "add submodules"', tmp)

    if origin_url:
        _run('remote add origin {}'.format(origin_url), tmp)

    commit = _run('rev-list HEAD -n 1', tmp)
    return tmp.replace("\\", "/"), commit


def git_add_changes_commit(folder, msg="fix"):
    cwd = os.getcwd()
    try:
        os.chdir(folder)
        # Make sure user and email exist, otherwise it can error
        check_output_runner('git config user.name "Your Name"')
        check_output_runner('git config user.email "you@example.com"')
        check_output_runner('git add . && git commit -m "{}"'.format(msg))
        return check_output_runner("git rev-parse HEAD").strip()
    finally:
        os.chdir(cwd)
