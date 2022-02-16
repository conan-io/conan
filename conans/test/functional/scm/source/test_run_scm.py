# coding=utf-8

import os
import unittest

import mock
import pytest

from conans.cli.output import ConanOutput
from conans.client.source import _run_cache_scm
from conans.client.tools.scm import Git
from conans.model.scm import SCM
from conans.test.utils.mocks import RedirectedTestOutput
from conans.test.utils.scm import create_local_git_repo
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import redirect_output


@pytest.mark.tool("git")
class RunSCMTest(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = temp_folder()
        self.src_folder = os.path.join(self.tmp_dir, 'source')

    def test_in_cache_with_local_sources(self):
        """In cache, if we have cached scm sources in the scm_sources, it will get them"""
        output = RedirectedTestOutput()
        with redirect_output(output):
            local_sources_path = self.tmp_dir.replace('\\', '/')

            # Mock the conanfile (return scm_data)
            conanfile = mock.MagicMock()
            conanfile.output = ConanOutput()
            conanfile.scm = {'type': 'git', 'url': 'auto', 'revision': 'auto'}
            conanfile.folders.base_source = self.src_folder

            # Mock functions called from inside _run_scm (tests will be here)
            def merge_directories(src, dst, excluded=None):
                self.assertEqual(src, local_sources_path)
                self.assertEqual(dst, self.src_folder)

            def clean_source_folder(folder):
                self.assertEqual(folder, self.src_folder)

            with mock.patch("conans.client.source.merge_directories", side_effect=merge_directories):
                with mock.patch("conans.client.source._clean_source_folder",
                                side_effect=clean_source_folder):
                    _run_cache_scm(conanfile, scm_sources_folder=local_sources_path)

        self.assertIn("Copying previously cached scm sources", output)

    def test_in_cache_no_local_sources(self):
        """In cache, if we DON'T have cached scm sources in the scm_sources, it will clone"""

        output = RedirectedTestOutput()
        with redirect_output(output):
            # Mock the conanfile (return scm_data)
            subfolder = 'subfolder'
            url = 'whatever'
            conanfile = mock.MagicMock()
            conanfile.output = ConanOutput()
            conanfile.scm = {'type': 'git', 'url': url, 'revision': 'auto', 'subfolder': subfolder}
            conanfile.folders.base_source = self.src_folder

            # Mock functions called from inside _run_scm (tests will be here)
            def clean_source_folder(folder):
                self.assertEqual(folder, os.path.join(self.src_folder, subfolder))

            def scm_checkout(scm_itself):
                self.assertEqual(scm_itself.repo_folder, os.path.join(self.src_folder, subfolder))

            with mock.patch("conans.client.source._clean_source_folder",
                            side_effect=clean_source_folder):
                with mock.patch.object(SCM, "checkout", new=scm_checkout):
                    _run_cache_scm(conanfile,
                                   scm_sources_folder="/not/existing/path")

        self.assertIn("SCM: Getting sources from url: '{}'".format(url), output)
