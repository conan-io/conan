import os

from conans.test.utils.test_files import temp_folder
from conans.util.files import save_files
from conans.util.runners import check_output_runner, muted_runner


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
                          tags=None, origin_url=None):
    tmp = folder or temp_folder()
    if files:
        save_files(tmp, files)

    muted_runner("git init .", folder=tmp)
    muted_runner('git config user.name "Your Name"', folder=tmp)
    muted_runner('git config user.email "you@example.com"', folder=tmp)

    if branch:
        muted_runner("git checkout -b %s" % branch, folder=tmp)

    muted_runner("git add .")
    for i in range(0, commits):
        muted_runner('git commit --allow-empty -m "commiting"', folder=tmp)

    tags = tags or []
    for tag in tags:
        muted_runner("git tag %s" % tag, folder=tmp)

    if submodules:
        for submodule in submodules:
            muted_runner('git submodule add "%s"' % submodule, folder=tmp)
        muted_runner('git commit -m "add submodules"', folder=tmp)

    if origin_url:
        muted_runner('git remote add origin {}'.format(origin_url), folder=tmp)

    commit = check_output_runner('git rev-list HEAD -n 1', folder=tmp)
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
