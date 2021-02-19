# coding=utf-8

import os
import unittest

import mock
import pytest
from parameterized import parameterized

from conans.client.cmd.export import _capture_scm_auto_fields
from conans.client.tools.scm import Git
from conans.model.ref import ConanFileReference
from conans.test.utils.mocks import TestBufferConanOutput
from conans.test.utils.scm import create_local_git_repo
from conans.test.utils.test_files import temp_folder
from conans.util.files import save


@pytest.mark.tool_git
@mock.patch("conans.client.cmd.export._replace_scm_data_in_recipe", return_value=None)
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

    @parameterized.expand([(True, ), (False, )])
    def test_url_auto_revision_auto(self, _, local_origin):
        output = TestBufferConanOutput()

        # Mock the conanfile (return scm_data)
        conanfile = mock.MagicMock()
        conanfile.scm = {'type': 'git', 'url': 'auto', 'revision': 'auto'}

        # Set the remote for the repo
        url = self.git.folder if local_origin else "https://remote.url"
        self.git.run("remote add origin \"{}\"".format(url))

        scm_data, _ = _capture_scm_auto_fields(
            conanfile=conanfile,
            conanfile_dir=self.conanfile_dir,
            package_layout=None,
            output=output,
            ignore_dirty=True,
            scm_to_conandata=False)

        self.assertEqual(scm_data.url, url)
        self.assertEqual(scm_data.revision, self.rev)
        self.assertIn("Repo origin deduced by 'auto': {}".format(url), output)
        self.assertIn("Revision deduced by 'auto': {}".format(self.rev), output)
        if local_origin:
            self.assertIn("WARN: Repo origin looks like a local path: {}".format(url), output)

    @parameterized.expand([(True, ), (False, ), ])
    def test_revision_auto(self, _, is_pristine):
        output = TestBufferConanOutput()

        # Mock the conanfile (return scm_data)
        url = "https://remote.url"
        conanfile = mock.MagicMock()
        conanfile.scm = {'type': 'git', 'url': url, 'revision': 'auto'}

        if not is_pristine:
            save(os.path.join(self.git.folder, "other"), "ccc")

        scm_data, _ = _capture_scm_auto_fields(
            conanfile=conanfile,
            conanfile_dir=self.conanfile_dir,
            package_layout=None,
            output=output,
            ignore_dirty=False,
            scm_to_conandata=False)

        self.assertEqual(scm_data.url, url)
        if is_pristine:
            self.assertEqual(scm_data.revision, self.rev)
            self.assertIn("Revision deduced by 'auto': {}".format(self.rev), output)
            self.assertNotIn("Repo origin deduced", output)
        else:
            self.assertEqual(scm_data.revision, "auto")
            self.assertIn("There are uncommitted changes, skipping the replacement of 'scm.url' "
                          "and 'scm.revision' auto fields. Use --ignore-dirty to force it.",
                          output)

    def test_url_auto(self, _):
        output = TestBufferConanOutput()

        # Mock the conanfile (return scm_data)
        conanfile = mock.MagicMock()
        conanfile.scm = {'type': 'git', 'url': "auto", 'revision': self.rev}

        # Set the remote for the repo
        url = "https://remote.url"
        self.git.run("remote add origin \"{}\"".format(url))

        scm_data, _ = _capture_scm_auto_fields(
                    conanfile=conanfile,
                    conanfile_dir=self.conanfile_dir,
                    package_layout=None,
                    output=output,
                    ignore_dirty=True,
                    scm_to_conandata=False)

        self.assertEqual(scm_data.url, url)
        self.assertEqual(scm_data.revision, self.rev)
        self.assertIn("Repo origin deduced by 'auto': {}".format(url), output)
        self.assertNotIn("Revision deduced", output)
