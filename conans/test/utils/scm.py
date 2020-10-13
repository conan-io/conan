import errno
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
import uuid

from six.moves.urllib.parse import quote

from conans.client.tools import get_cased_path, Git, chdir, SVN
from conans.test.utils.test_files import temp_folder
from conans.util.files import save_files, mkdir
from conans.util.runners import check_output_runner


def create_local_git_repo(files=None, branch=None, submodules=None, folder=None, commits=1,
                          tags=None, origin_url=None):
    tmp = folder or temp_folder()
    tmp = get_cased_path(tmp)
    if files:
        save_files(tmp, files)
    git = Git(tmp)
    git.run("init .")
    git.run('config user.email "you@example.com"')
    git.run('config user.name "Your Name"')

    if branch:
        git.run("checkout -b %s" % branch)

    git.run("add .")
    for i in range(0, commits):
        git.run('commit --allow-empty -m "commiting"')

    tags = tags or []
    for tag in tags:
        git.run("tag %s" % tag)

    if submodules:
        for submodule in submodules:
            git.run('submodule add "%s"' % submodule)
        git.run('commit -m "add submodules"')

    if origin_url:
        git.run('remote add origin {}'.format(origin_url))

    return tmp.replace("\\", "/"), git.get_revision()


def create_local_svn_checkout(files, repo_url, rel_project_path=None,
                              commit_msg='default commit message', delete_checkout=True,
                              folder=None):
    tmp_dir = folder or temp_folder()
    try:
        rel_project_path = rel_project_path or str(uuid.uuid4())
        # Do not use SVN class as it is what we will be testing
        subprocess.check_output('svn co "{url}" "{path}"'.format(url=repo_url,
                                                                 path=tmp_dir),
                                shell=True)
        tmp_project_dir = os.path.join(tmp_dir, rel_project_path)
        mkdir(tmp_project_dir)
        save_files(tmp_project_dir, files)
        with chdir(tmp_project_dir):
            subprocess.check_output("svn add .", shell=True)
            subprocess.check_output('svn commit -m "{}"'.format(commit_msg), shell=True)
            if SVN.get_version() >= SVN.API_CHANGE_VERSION:
                rev = check_output_runner("svn info --show-item revision").strip()
            else:
                import xml.etree.ElementTree as ET
                output = check_output_runner("svn info --xml").strip()
                root = ET.fromstring(output)
                rev = root.findall("./entry")[0].get("revision")
        project_url = repo_url + "/" + quote(rel_project_path.replace("\\", "/"))
        return project_url, rev
    finally:
        if delete_checkout:
            shutil.rmtree(tmp_dir, ignore_errors=False, onerror=try_remove_readonly)


def create_remote_svn_repo(folder=None):
    tmp_dir = folder or temp_folder()
    subprocess.check_output('svnadmin create "{}"'.format(tmp_dir), shell=True)
    return SVN.file_protocol + quote(tmp_dir.replace("\\", "/"), safe='/:')


class SVNLocalRepoTestCase(unittest.TestCase):
    path_with_spaces = True

    def _create_local_svn_repo(self):
        folder = os.path.join(self._tmp_folder, 'repo_server')
        return create_remote_svn_repo(folder)

    def gimme_tmp(self, create=True):
        tmp = os.path.join(self._tmp_folder, str(uuid.uuid4()))
        if create:
            os.makedirs(tmp)
        return tmp

    def create_project(self, files, rel_project_path=None, commit_msg='default commit message',
                       delete_checkout=True):
        tmp_dir = self.gimme_tmp()
        return create_local_svn_checkout(files, self.repo_url, rel_project_path=rel_project_path,
                                         commit_msg=commit_msg, delete_checkout=delete_checkout,
                                         folder=tmp_dir)

    def run(self, *args, **kwargs):
        tmp_folder = tempfile.mkdtemp(suffix='_conans')
        try:
            self._tmp_folder = os.path.join(tmp_folder, 'path with spaces'
                                            if self.path_with_spaces else 'pathwithoutspaces')
            os.makedirs(self._tmp_folder)
            self.repo_url = self._create_local_svn_repo()
            super(SVNLocalRepoTestCase, self).run(*args, **kwargs)
        finally:
            shutil.rmtree(tmp_folder, ignore_errors=False, onerror=try_remove_readonly)


def try_remove_readonly(func, path, exc):  # TODO: May promote to conan tools?
    # src: https://stackoverflow.com/questions/1213706/what-user-do-python-scripts-run-as-in-windows
    excvalue = exc[1]
    if func in (os.rmdir, os.remove, os.unlink) and excvalue.errno == errno.EACCES:
        os.chmod(path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)  # 0777
        func(path)
    else:
        raise OSError("Cannot make read-only %s" % path)
