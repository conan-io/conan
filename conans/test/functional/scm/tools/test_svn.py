# coding=utf-8

import os
import re
import shutil
import subprocess
import unittest
import uuid

import pytest
import six
from mock import patch
from six.moves.urllib.parse import quote

from conans.client.tools.scm import SVN
from conans.errors import ConanException
from conans.model.version import Version
from conans.test.utils.scm import SVNLocalRepoTestCase, try_remove_readonly
from conans.test.utils.tools import temp_folder, TestClient
from conans.util.files import save


class SVNRemoteUrlTest(unittest.TestCase):

    def test_remove_credentials(self):
        """ Check that the 'remove_credentials' argument is taken into account """
        expected_url = 'https://myrepo.com/path/to/repo'
        origin_url = 'https://username:password@myrepo.com/path/to/repo'

        svn = SVN(folder=temp_folder())

        # Mocking, as we cannot change SVN remote to a non-existing url
        with patch.object(svn, '_show_item', return_value=origin_url):
            self.assertEqual(svn.get_remote_url(), origin_url)
            self.assertEqual(svn.get_remote_url(remove_credentials=True), expected_url)


@pytest.mark.slow
@pytest.mark.tool_svn
class SVNToolTestsBasic(SVNLocalRepoTestCase):

    @patch('subprocess.Popen')
    def test_version(self, mocked_open):
        svn_version_string = """svn, version 1.10.3 (r1842928)
compiled Apr  5 2019, 18:59:58 on x86_64-apple-darwin17.0.0"""
        mocked_open.return_value.communicate.return_value = (svn_version_string.encode(), None)
        version = SVN.get_version()
        self.assertEqual(version, "1.10.3")

    @patch('subprocess.Popen')
    def test_version_invalid(self, mocked_open):
        mocked_open.return_value.communicate.return_value = ('failed'.encode(), None)
        with self.assertRaises(ConanException):
            SVN.get_version()

    def test_check_svn_repo(self):
        project_url, _ = self.create_project(files={'myfile': "contents"})
        tmp_folder = self.gimme_tmp()
        svn = SVN(folder=tmp_folder)
        pattern = "'{0}' is not a valid 'svn' repository".format(re.escape(tmp_folder))
        with six.assertRaisesRegex(self, ConanException, pattern):
            svn.check_repo()
        svn.checkout(url=project_url)
        try:
            svn.check_repo()
        except Exception:
            self.fail("After checking out, it should be a valid SVN repository")

    def test_clone(self):
        project_url, _ = self.create_project(files={'myfile': "contents"})
        tmp_folder = self.gimme_tmp()
        svn = SVN(folder=tmp_folder)
        svn.checkout(url=project_url)
        self.assertTrue(os.path.exists(os.path.join(tmp_folder, 'myfile')))

    def test_svn_revision_message(self):
        tmp_folder = self.gimme_tmp()
        svn = SVN(folder=tmp_folder)
        svn.checkout(url=self.repo_url)
        self.assertIsNone(svn.get_revision_message())

        new_file = os.path.join(tmp_folder, "new_file")
        with open(new_file, "w") as f:
            f.write("content")

        svn.run('add new_file')
        svn.run('commit -m "add to file"')
        svn.run('update')
        self.assertEqual("add to file", svn.get_revision_message())

    def test_revision_number(self):
        svn = SVN(folder=self.gimme_tmp())
        svn.checkout(url=self.repo_url)
        rev = int(svn.get_revision())
        self.create_project(files={'another_file': "content"})
        svn.run("update")
        rev2 = int(svn.get_revision())
        self.assertEqual(rev2, rev + 1)

    def test_repo_url(self):
        svn = SVN(folder=self.gimme_tmp())
        svn.checkout(url=self.repo_url)
        remote_url = svn.get_remote_url()
        self.assertEqual(remote_url.lower(), self.repo_url.lower())

        svn2 = SVN(folder=self.gimme_tmp(create=False))
        svn2.checkout(url=remote_url)  # clone using quoted url
        self.assertEqual(svn2.get_remote_url().lower(), self.repo_url.lower())

    def test_repo_project_url(self):
        project_url, _ = self.create_project(files={"myfile": "content"})
        svn = SVN(folder=self.gimme_tmp())
        svn.checkout(url=project_url)
        self.assertEqual(svn.get_remote_url().lower(), project_url.lower())

    def test_checkout(self):
        # Ensure we have several revisions in the repository
        self.create_project(files={'file': "content"})
        self.create_project(files={'file': "content"})
        svn = SVN(folder=self.gimme_tmp())
        svn.checkout(url=self.repo_url)
        rev = int(svn.get_revision())
        svn.update(revision=rev - 1)  # Checkout previous revision
        self.assertTrue(int(svn.get_revision()), rev-1)

    def test_clone_over_dirty_directory(self):
        project_url, _ = self.create_project(files={'myfile': "contents"})
        tmp_folder = self.gimme_tmp()
        svn = SVN(folder=tmp_folder)
        svn.checkout(url=project_url)

        new_file = os.path.join(tmp_folder, "new_file")
        with open(new_file, "w") as f:
            f.write("content")

        mod_file = os.path.join(tmp_folder, "myfile")
        with open(mod_file, "a") as f:
            f.write("new content")

        self.assertFalse(svn.is_pristine())
        # SVN::clone over a dirty repo reverts all changes
        # (but it doesn't delete non versioned files)
        svn.checkout(url=project_url)
        self.assertEqual(open(mod_file).read(), "contents")
        self.assertFalse(svn.is_pristine())

    def test_excluded_files(self):
        project_url, _ = self.create_project(files={'myfile': "contents"})
        tmp_folder = self.gimme_tmp()
        svn = SVN(folder=tmp_folder)
        svn.checkout(url=project_url)

        # Add untracked file
        new_file = os.path.join(tmp_folder, str(uuid.uuid4()))
        with open(new_file, "w") as f:
            f.write("content")

        # Add ignore file
        file_to_ignore = str(uuid.uuid4())
        with open(os.path.join(tmp_folder, file_to_ignore), "w") as f:
            f.write("content")
        svn.run("propset svn:ignore {} .".format(file_to_ignore))
        svn.run('commit -m "add ignored file"')

        excluded_files = svn.excluded_files()
        self.assertIn(file_to_ignore, excluded_files)
        self.assertNotIn('.svn', excluded_files)
        self.assertEqual(len(excluded_files), 1)

    def test_credentials(self):
        svn = SVN(folder=self.gimme_tmp(), username="ada", password="lovelace")
        url_credentials = svn.get_url_with_credentials("https://some.url.com")
        self.assertEqual(url_credentials, "https://ada:lovelace@some.url.com")

    def test_verify_ssl(self):
        class MyRunner(object):
            def __init__(self, svn):
                self.calls = []
                self._runner = svn._runner
                svn._runner = self

            def __call__(self, command, *args, **kwargs):
                self.calls.append(command)
                return self._runner(command, *args, **kwargs)

        project_url, _ = self.create_project(files={'myfile': "contents",
                                                    'subdir/otherfile': "content"})

        svn = SVN(folder=self.gimme_tmp(), username="peter", password="otool", verify_ssl=True)
        runner = MyRunner(svn)
        svn.checkout(url=project_url)
        self.assertNotIn("--trust-server-cert-failures=unknown-ca", runner.calls[1])

        svn = SVN(folder=self.gimme_tmp(), username="peter", password="otool", verify_ssl=False)
        runner = MyRunner(svn)
        svn.checkout(url=project_url)
        if svn.version >= SVN.API_CHANGE_VERSION:
            self.assertIn("--trust-server-cert-failures=unknown-ca", runner.calls[1])
        else:
            self.assertIn("--trust-server-cert", runner.calls[1])

    def test_repo_root(self):
        project_url, _ = self.create_project(files={'myfile': "contents",
                                                    'subdir/otherfile': "content"})
        tmp_folder = self.gimme_tmp()
        svn = SVN(folder=tmp_folder)
        svn.checkout(url=project_url)

        path = os.path.realpath(tmp_folder).replace('\\', '/').lower()
        self.assertEqual(path, svn.get_repo_root().lower())

        # SVN instantiated in a subfolder
        svn2 = SVN(folder=os.path.join(tmp_folder, 'subdir'))
        self.assertFalse(svn2.folder == tmp_folder)
        path = os.path.realpath(tmp_folder).replace('\\', '/').lower()
        self.assertEqual(path, svn2.get_repo_root().lower())

    def test_is_local_repository(self):
        svn = SVN(folder=self.gimme_tmp())
        svn.checkout(url=self.repo_url)
        self.assertTrue(svn.is_local_repository())

        # TODO: Test not local repository

    def test_last_changed_revision(self):
        project_url, _ = self.create_project(files={'project1/myfile': "contents",
                                                    'project2/myfile': "content",
                                                    'project2/subdir1/myfile': "content",
                                                    'project2/subdir2/myfile': "content",
                                                    })
        prj1 = SVN(folder=self.gimme_tmp())
        prj1.checkout(url='/'.join([project_url, 'project1']))

        prj2 = SVN(folder=self.gimme_tmp())
        prj2.checkout(url='/'.join([project_url, 'project2']))

        self.assertEqual(prj1.get_last_changed_revision(), prj2.get_last_changed_revision())

        # Modify file in one subfolder of prj2
        with open(os.path.join(prj2.folder, "subdir1", "myfile"), "a") as f:
            f.write("new content")
        prj2.run('commit -m "add to file"')
        prj2.run('update')
        prj1.run('update')

        self.assertNotEqual(prj1.get_last_changed_revision(), prj2.get_last_changed_revision())
        self.assertEqual(prj1.get_revision(), prj2.get_revision())

        # Instantiate a SVN in the other subfolder
        prj2_subdir2 = SVN(folder=os.path.join(prj2.folder, "subdir2"))
        prj2_subdir2.run('update')
        self.assertEqual(prj2.get_last_changed_revision(),
                         prj2_subdir2.get_last_changed_revision())
        self.assertNotEqual(prj2.get_last_changed_revision(use_wc_root=False),
                            prj2_subdir2.get_last_changed_revision(use_wc_root=False))

    def test_branch(self):
        project_url, _ = self.create_project(files={'prj1/trunk/myfile': "contents",
                                                    'prj1/branches/my_feature/myfile': "",
                                                    'prj1/branches/issue3434/myfile': "",
                                                    'prj1/tags/v12.3.4/myfile': "",
                                                    })
        svn = SVN(folder=self.gimme_tmp())
        svn.checkout(url='/'.join([project_url, 'prj1', 'trunk']))
        self.assertEqual("trunk", svn.get_branch())

        svn = SVN(folder=self.gimme_tmp())
        svn.checkout(url='/'.join([project_url, 'prj1', 'branches', 'my_feature']))
        self.assertEqual("my_feature", svn.get_branch())

        svn = SVN(folder=self.gimme_tmp())
        svn.checkout(url='/'.join([project_url, 'prj1', 'branches', 'issue3434']))
        self.assertEqual("issue3434", svn.get_branch())

        svn = SVN(folder=self.gimme_tmp())
        svn.checkout(url='/'.join([project_url, 'prj1', 'tags', 'v12.3.4']))
        self.assertIsNone(svn.get_branch())

        svn = SVN(folder=self.gimme_tmp())
        with six.assertRaisesRegex(self, ConanException, "Unable to get svn branch"):
            svn.get_branch()

    def test_tag(self):
        project_url, _ = self.create_project(files={'prj1/trunk/myfile': "contents",
                                                    'prj1/branches/my_feature/myfile': "",
                                                    'prj1/branches/issue3434/myfile': "",
                                                    'prj1/tags/v12.3.4/myfile': "",
                                                    })
        svn = SVN(folder=self.gimme_tmp())
        svn.checkout(url='/'.join([project_url, 'prj1', 'trunk']))
        self.assertIsNone(svn.get_tag())

        svn = SVN(folder=self.gimme_tmp())
        svn.checkout(url='/'.join([project_url, 'prj1', 'branches', 'my_feature']))
        self.assertIsNone(svn.get_tag())

        svn = SVN(folder=self.gimme_tmp())
        svn.checkout(url='/'.join([project_url, 'prj1', 'branches', 'issue3434']))
        self.assertIsNone(svn.get_tag())

        svn = SVN(folder=self.gimme_tmp())
        svn.checkout(url='/'.join([project_url, 'prj1', 'tags', 'v12.3.4']))
        self.assertEqual("v12.3.4", svn.get_tag())

        svn = SVN(folder=self.gimme_tmp())
        with six.assertRaisesRegex(self, ConanException, "Unable to get svn tag"):
            svn.get_tag()


@pytest.mark.slow
@pytest.mark.tool_svn
class SVNToolTestsBasicOldVersion(SVNToolTestsBasic):
    def run(self, *args, **kwargs):
        try:
            setattr(SVN, '_version', Version("1.5"))
            self.assertTrue(SVN().version < SVN.API_CHANGE_VERSION)
            super(SVNToolTestsBasicOldVersion, self).run(*args, **kwargs)
        finally:
            delattr(SVN, '_version')
            assert SVN().version == SVN.get_version(), \
                "{} != {}".format(SVN().version, SVN.get_version())

    # Do not add tests to this class, all should be compatible with new version of SVN


@pytest.mark.slow
@pytest.mark.tool_svn
class SVNToolTestsPristine(SVNLocalRepoTestCase):

    def setUp(self):
        unittest.skipUnless(SVN.get_version() >= SVN.API_CHANGE_VERSION,
                            "SVN::is_pristine not implemented")

    def test_checkout(self):
        svn = SVN(folder=self.gimme_tmp())
        svn.checkout(url=self.repo_url)
        self.assertTrue(svn.is_pristine())

    def test_checkout_project(self):
        project_url, _ = self.create_project(files={'myfile': "contents"})

        tmp_folder = self.gimme_tmp()
        svn = SVN(folder=tmp_folder)
        svn.checkout(url=project_url)
        self.assertTrue(svn.is_pristine())

    def test_modified_file(self):
        project_url, _ = self.create_project(files={'myfile': "contents"})
        tmp_folder = self.gimme_tmp()
        svn = SVN(folder=tmp_folder)
        svn.checkout(url=project_url)
        with open(os.path.join(tmp_folder, "myfile"), "a") as f:
            f.write("new content")
        self.assertFalse(svn.is_pristine())

    def test_untracked_file(self):
        self.create_project(files={'myfile': "contents"})
        tmp_folder = self.gimme_tmp()
        svn = SVN(folder=tmp_folder)
        svn.checkout(url=self.repo_url)
        self.assertTrue(svn.is_pristine())
        with open(os.path.join(tmp_folder, "not_tracked.txt"), "w") as f:
            f.write("content")
        self.assertFalse(svn.is_pristine())

    def test_ignored_file(self):
        tmp_folder = self.gimme_tmp()
        svn = SVN(folder=self.gimme_tmp())
        svn.checkout(url=self.repo_url)
        file_to_ignore = "secret.txt"
        with open(os.path.join(tmp_folder, file_to_ignore), "w") as f:
            f.write("content")
        svn.run("propset svn:ignore {} .".format(file_to_ignore))
        self.assertFalse(svn.is_pristine())  # Folder properties have been modified
        svn.run('commit -m "add ignored file"')
        self.assertTrue(svn.is_pristine())

    def test_conflicted_file(self):
        project_url, _ = self.create_project(files={'myfile': "contents"})

        def work_on_project(tmp_folder):
            svn = SVN(folder=tmp_folder)
            svn.checkout(url=project_url)
            self.assertTrue(svn.is_pristine())
            with open(os.path.join(tmp_folder, "myfile"), "a") as f:
                f.write("random content: {}".format(uuid.uuid4()))
            return svn

        # Two users working on the same project
        svn1 = work_on_project(self.gimme_tmp())
        svn2 = work_on_project(self.gimme_tmp())

        # User1 is faster
        svn1.run('commit -m "user1 commit"')
        self.assertFalse(svn1.is_pristine())
        # Yes, we need to update local copy in order to have the same revision everywhere.
        svn1.run('update')
        self.assertTrue(svn1.is_pristine())

        # User2 updates and get a conflicted file
        svn2.run('update')
        self.assertFalse(svn2.is_pristine())
        svn2.run('revert . -R')
        self.assertTrue(svn2.is_pristine())

    def test_mixed_revisions(self):
        project_url, _ = self.create_project(files={'myfile': "cc", 'another': 'aa'})
        svn = SVN(folder=self.gimme_tmp())
        svn.checkout(url=project_url)
        with open(os.path.join(svn.folder, 'myfile'), "a") as f:
            f.write('more')
        svn.run('commit -m "up version"')
        self.assertFalse(svn.is_pristine())

    def test_missing_remote(self):
        repo_url = self.gimme_tmp()
        subprocess.check_output('svnadmin create "{}"'.format(repo_url), shell=True)
        project_url = SVN.file_protocol + quote(repo_url.replace("\\", "/"), safe='/:')

        svn = SVN(folder=self.gimme_tmp())
        svn.checkout(url=project_url)
        self.assertTrue(svn.is_pristine())

        shutil.rmtree(repo_url, ignore_errors=False, onerror=try_remove_readonly)
        self.assertFalse(os.path.exists(repo_url))
        self.assertFalse(svn.is_pristine())


@pytest.mark.tool_svn
class SVNToolTestsPristineWithExternalFile(SVNLocalRepoTestCase):

    def _propset_cmd(self, relpath, rev, url):
        return 'propset svn:externals "{} -r{} {}" .'.format(relpath, rev, url)

    def setUp(self):
        project_url, _ = self.create_project(files={'myfile': "contents"})
        project2_url, rev = self.create_project(files={'nestedfile': "contents"})

        self.svn = SVN(folder=self.gimme_tmp())
        self.svn.checkout(url=project_url)
        self.svn.run(self._propset_cmd("subrepo_nestedfile", rev, project2_url + '/nestedfile'))
        self.svn.run('commit -m "add external"')
        self.svn.update()
        self.assertTrue(self.svn.is_pristine())

    def test_modified_external(self):
        with open(os.path.join(self.svn.folder, "subrepo_nestedfile"), "a") as f:
            f.write("cosass")
        self.assertFalse(self.svn.is_pristine())


@pytest.mark.tool_svn
class SVNToolTestsPristineWithExternalsNotFixed(SVNLocalRepoTestCase):

    def _propset_cmd(self, relpath, url):
        return 'propset svn:externals "{} {}" .'.format(relpath, url)

    def setUp(self):
        project_url, _ = self.create_project(files={'myfile': "contents"})
        project2_url, _ = self.create_project(files={'nestedfile': "contents"})

        self.svn = SVN(folder=self.gimme_tmp())
        self.svn.checkout(url=project_url)
        self.svn.run(self._propset_cmd("subrepo", project2_url))
        self.svn.run('commit -m "add external"')
        self.svn.update()
        self.assertTrue(self.svn.is_pristine())

        self.svn2 = SVN(folder=self.gimme_tmp())
        self.svn2.checkout(url=project2_url)
        self.assertTrue(self.svn.is_pristine())

    def test_modified_external(self):
        with open(os.path.join(self.svn2.folder, "nestedfile"), "a") as f:
            f.write("cosass")
        self.svn2.run('commit -m "another"')
        self.svn2.update()
        self.assertTrue(self.svn2.is_pristine())

        # Known: without fixed external, it won't be pristine if there is something new in remote.
        self.assertFalse(self.svn.is_pristine())


@pytest.mark.tool_svn
class SVNToolTestsPristineWithExternalsFixed(SVNLocalRepoTestCase):

    def _propset_cmd(self, relpath, rev, url):
        return 'propset svn:externals "{} -r{} {}" .'.format(relpath, rev, url)

    def setUp(self):
        project_url, _ = self.create_project(files={'myfile': "contents"})
        project2_url, rev = self.create_project(files={'nestedfile': "contents"})

        self.svn = SVN(folder=self.gimme_tmp())
        self.svn.checkout(url=project_url)
        self.svn.run(self._propset_cmd("subrepo", rev, project2_url))
        self.svn.run('commit -m "add external"')
        self.svn.update()
        self.assertTrue(self.svn.is_pristine())

        self.svn_subrepo = SVN(folder=os.path.join(self.svn.folder, 'subrepo'))
        self.assertTrue(self.svn_subrepo.is_pristine())

    def test_modified_external(self):
        with open(os.path.join(self.svn.folder, "subrepo", "nestedfile"), "a") as f:
            f.write("cosass")
        self.assertFalse(self.svn_subrepo.is_pristine())
        self.assertFalse(self.svn.is_pristine())

    def test_commit_external(self):
        with open(os.path.join(self.svn.folder, "subrepo", "nestedfile"), "a") as f:
            f.write("cosass")
        self.svn_subrepo.run('commit -m "up external"')
        self.assertFalse(self.svn_subrepo.is_pristine())
        self.assertFalse(self.svn.is_pristine())

        self.svn_subrepo.update()
        self.assertTrue(self.svn_subrepo.is_pristine())
        self.assertFalse(self.svn.is_pristine())

    def test_untracked_external(self):
        with open(os.path.join(self.svn.folder, "subrepo", "other_file"), "w") as f:
            f.write("cosass")
        self.assertFalse(self.svn_subrepo.is_pristine())
        self.assertFalse(self.svn.is_pristine())

    def test_ignored_external(self):
        file_to_ignore = "secret.txt"
        with open(os.path.join(self.svn_subrepo.folder, file_to_ignore), "w") as f:
            f.write("cosas")

        self.svn_subrepo.run("propset svn:ignore {} .".format(file_to_ignore))
        self.assertFalse(self.svn_subrepo.is_pristine())
        self.assertFalse(self.svn.is_pristine())

        self.svn_subrepo.run('commit -m "add ignored file"')
        self.assertTrue(self.svn_subrepo.is_pristine())
        self.assertFalse(self.svn.is_pristine())

        subrepo_rev = self.svn_subrepo.get_revision()
        self.svn.run(self._propset_cmd("subrepo", subrepo_rev, self.svn_subrepo.get_remote_url()))
        self.assertTrue(self.svn_subrepo.is_pristine())
        self.assertFalse(self.svn.is_pristine())

        self.svn.run('commit -m "change property"')
        self.svn.update()
        self.assertTrue(self.svn.is_pristine())


@pytest.mark.slow
@pytest.mark.tool_svn
class SVNToolsTestsRecipe(SVNLocalRepoTestCase):

    conanfile = """
import os
from conans import ConanFile, tools

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    exports_sources = "other"

    def source(self):
        svn = tools.SVN({svn_folder})
        svn.checkout(url="{svn_url}")

    def build(self):
        assert(os.path.exists("{file_path}"))
        assert(os.path.exists("other"))
"""

    def test_clone_root_folder(self):
        tmp_folder = self.gimme_tmp()
        client = TestClient()
        client.run_command('svn co "{}" "{}"'.format(self.repo_url, tmp_folder))
        save(os.path.join(tmp_folder, "file.h"), "contents")
        client.run_command("svn add file.h", cwd=tmp_folder)
        client.run_command('svn commit -m "message"', cwd=tmp_folder)

        conanfile = self.conanfile.format(svn_folder="", svn_url=self.repo_url,
                                          file_path="file.h")
        client.save({"conanfile.py": conanfile, "other": "hello"})
        client.run("create . user/channel")

    def test_clone_subfolder(self):
        tmp_folder = self.gimme_tmp()
        client = TestClient()
        client.run_command('svn co "{}" "{}"'.format(self.repo_url, tmp_folder))
        save(os.path.join(tmp_folder, "file.h"), "contents")
        client.run_command("svn add file.h", cwd=tmp_folder)
        client.run_command('svn commit -m "message"', cwd=tmp_folder)

        conanfile = self.conanfile.format(svn_folder="\"src\"", svn_url=self.repo_url,
                                          file_path="src/file.h")
        client.save({"conanfile.py": conanfile, "other": "hello"})
        client.run("create . user/channel")
