# coding=utf-8

import os
import unittest

import mock

from conans.client.source import _run_scm
from conans.client.tools.scm import Git
from conans.model.scm import SCM
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import create_local_git_repo, TestBufferConanOutput


class RunSCMTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = temp_folder()
        self.src_folder = os.path.join(self.tmp_dir, 'source')

    def test_in_cache_with_local_sources(self):
        output = TestBufferConanOutput()
        local_sources_path = self.tmp_dir.replace('\\', '/')

        # Mock the conanfile (return scm_data)
        conanfile = mock.MagicMock()
        conanfile.scm = {'type': 'git', 'url': 'auto', 'revision': 'auto'}

        # Mock functions called from inside _run_scm (tests will be here)
        def merge_directories(src, dst, excluded=None):
            self.assertEqual(src, local_sources_path)
            self.assertEqual(dst, self.src_folder)

        def clean_source_folder(folder):
            self.assertEqual(folder, self.src_folder)

        with mock.patch("conans.client.source.merge_directories", side_effect=merge_directories):
            with mock.patch("conans.client.source._clean_source_folder",
                            side_effect=clean_source_folder):
                _run_scm(conanfile=conanfile,
                         src_folder=self.src_folder,
                         local_sources_path=local_sources_path,
                         output=output,
                         cache=True)

        self.assertIn("Getting sources from folder: {}".format(local_sources_path), output)

    def test_in_cache_no_local_sources(self):
        output = TestBufferConanOutput()

        # Mock the conanfile (return scm_data)
        subfolder = 'subfolder'
        url = 'whatever'
        conanfile = mock.MagicMock()
        conanfile.scm = {'type': 'git', 'url': url, 'revision': 'auto', 'subfolder': subfolder}

        # Mock functions called from inside _run_scm (tests will be here)
        def clean_source_folder(folder):
            self.assertEqual(folder, os.path.join(self.src_folder, subfolder))

        def scm_checkout(scm_itself):
            self.assertEqual(scm_itself.repo_folder, os.path.join(self.src_folder, subfolder))

        with mock.patch("conans.client.source._clean_source_folder",
                        side_effect=clean_source_folder):
            with mock.patch.object(SCM, "checkout", new=scm_checkout):
                _run_scm(conanfile=conanfile,
                         src_folder=self.src_folder,
                         local_sources_path=None,  # None or non existing path
                         output=output,
                         cache=True)

        self.assertIn("Getting sources from url: '{}'".format(url), output)

    def test_user_space_with_local_sources(self):
        output = TestBufferConanOutput()

        # Need a real repo to get a working SCM object
        local_sources_path = os.path.join(self.tmp_dir, 'git_repo').replace('\\', '/')
        create_local_git_repo(files={'file1': "content"}, folder=local_sources_path)
        git = Git(local_sources_path)
        url = "https://remote.url"
        git.run("remote add origin \"{}\"".format(url))

        # Mock the conanfile (return scm_data)
        conanfile = mock.MagicMock()
        conanfile.scm = {'type': 'git', 'url': 'auto', 'revision': 'auto'}

        # Mock functions called from inside _run_scm (tests will be here)
        def merge_directories(src, dst, excluded=None):
            src = os.path.normpath(src)
            dst = os.path.normpath(dst)
            self.assertEqual(src.replace('\\', '/'), local_sources_path)
            self.assertEqual(dst, self.src_folder)

        with mock.patch("conans.client.source.merge_directories", side_effect=merge_directories):
            _run_scm(conanfile=conanfile,
                     src_folder=self.src_folder,
                     local_sources_path=local_sources_path,
                     output=output,
                     cache=False)

        self.assertIn("getting sources from folder: {}".format(local_sources_path).lower(),
                      str(output).lower())

    def test_user_space_no_local_sources(self):
        output = TestBufferConanOutput()

        # Mock the conanfile (return scm_data)
        url = "https://remote.url"
        conanfile = mock.MagicMock()
        conanfile.scm = {'type': 'git', 'url': url, 'revision': '23333'}

        # Mock functions called from inside _run_scm (tests will be here)
        def scm_checkout(scm_itself):
            self.assertEqual(scm_itself.repo_folder, self.src_folder)

        with mock.patch.object(SCM, "checkout", new=scm_checkout):
            _run_scm(conanfile=conanfile,
                     src_folder=self.src_folder,
                     local_sources_path=None,
                     output=output,
                     cache=False)

        self.assertIn("Getting sources from url: '{}'".format(url), output)
