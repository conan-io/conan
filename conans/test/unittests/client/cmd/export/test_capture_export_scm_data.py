# coding=utf-8

import os
import unittest

import mock
from parameterized import parameterized

from conans.client.cmd.export import _capture_export_scm_data
from conans.client.tools.scm import Git
from conans.model.ref import ConanFileReference
from conans.paths import SCM_FOLDER
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import create_local_git_repo, TestBufferConanOutput
from conans.util.files import load, save


@mock.patch("conans.client.cmd.export._replace_scm_data_in_conanfile", return_value=None)
class CaptureExportSCMDataTest(unittest.TestCase):

    def setUp(self):
        ref = ConanFileReference.loads("name/version@user/channel")
        tmp_dir = temp_folder()

        # Need a real repo to get a working SCM object
        self.conanfile_dir = os.path.join(tmp_dir, 'git_repo').replace('\\', '/')
        self.git = Git(folder=self.conanfile_dir)
        self.origin, self.rev = create_local_git_repo(files={'file1': "content"},
                                                      folder=self.git.folder)

        # Mock the cache item (return the cache_ref_folder)
        self.cache_ref_folder = os.path.join(temp_folder(), ref.dir_repr())
        self.paths = mock.MagicMock(side_effect=None)
        self.paths.scm_folder.side_effect = lambda _: os.path.join(self.cache_ref_folder, SCM_FOLDER)

    @parameterized.expand([(True, ), (False, )])
    def test_url_auto_revision_auto(self, _, local_origin):
        output = TestBufferConanOutput()

        # Mock the conanfile (return scm_data)
        conanfile = mock.MagicMock()
        conanfile.scm = {'type': 'git', 'url': 'auto', 'revision': 'auto'}

        # Set the remote for the repo
        url = self.git.folder if local_origin else "https://remote.url"
        self.git.run("remote add origin \"{}\"".format(url))

        scm_data, captured_revision = _capture_export_scm_data(
            conanfile=conanfile,
            conanfile_dir=self.conanfile_dir,
            destination_folder="",
            output=output,
            paths=self.paths,
            ref=None)

        self.assertTrue(captured_revision)
        self.assertEquals(scm_data.url, url)
        self.assertEquals(scm_data.revision, self.rev)
        self.assertIn("Repo origin deduced by 'auto': {}".format(url), output)
        self.assertIn("Revision deduced by 'auto': {}".format(self.rev), output)
        if local_origin:
            self.assertIn("WARN: Repo origin looks like a local path: {}".format(url), output)

        scm_folder_file = os.path.join(self.cache_ref_folder, SCM_FOLDER)
        self.assertEqual(os.path.normcase(load(scm_folder_file)),
                         os.path.normcase(self.conanfile_dir))

    @parameterized.expand([(True, ), (False, ), ])
    def test_revision_auto(self, _, is_pristine):
        output = TestBufferConanOutput()

        # Mock the conanfile (return scm_data)
        url = "https://remote.url"
        conanfile = mock.MagicMock()
        conanfile.scm = {'type': 'git', 'url': url, 'revision': 'auto'}

        if not is_pristine:
            save(os.path.join(self.git.folder, "other"), "ccc")

        scm_data, captured_revision = _capture_export_scm_data(
            conanfile=conanfile,
            conanfile_dir=self.conanfile_dir,
            destination_folder="",
            output=output,
            paths=self.paths,
            ref=None)

        self.assertTrue(captured_revision)
        self.assertEquals(scm_data.url, url)
        self.assertEquals(scm_data.revision, self.rev)
        self.assertNotIn("Repo origin deduced", output)
        self.assertIn("Revision deduced by 'auto': {}".format(self.rev), output)
        if not is_pristine:
            self.assertIn("Repo status is not pristine: there might be modified files", output)

        scm_folder_file = os.path.join(self.cache_ref_folder, SCM_FOLDER)
        self.assertTrue(os.path.exists(scm_folder_file))
        self.assertEqual(os.path.normcase(load(scm_folder_file)),
                         os.path.normcase(self.conanfile_dir))

    def test_url_auto(self, _):
        output = TestBufferConanOutput()

        # Mock the conanfile (return scm_data)
        conanfile = mock.MagicMock()
        conanfile.scm = {'type': 'git', 'url': "auto", 'revision': self.rev}

        # Set the remote for the repo
        url = "https://remote.url"
        self.git.run("remote add origin \"{}\"".format(url))

        scm_data, captured_revision = _capture_export_scm_data(
            conanfile=conanfile,
            conanfile_dir=self.conanfile_dir,
            destination_folder="",
            output=output,
            paths=self.paths,
            ref=None)

        self.assertFalse(captured_revision)
        self.assertEquals(scm_data.url, url)
        self.assertEquals(scm_data.revision, self.rev)
        self.assertIn("Repo origin deduced by 'auto': {}".format(url), output)
        self.assertNotIn("Revision deduced", output)

        scm_folder_file = os.path.join(self.cache_ref_folder, SCM_FOLDER)
        self.assertTrue(os.path.exists(scm_folder_file))
        self.assertEqual(os.path.normcase(load(scm_folder_file)),
                         os.path.normcase(self.conanfile_dir))
