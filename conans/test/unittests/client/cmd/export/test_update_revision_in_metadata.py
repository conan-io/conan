# coding=utf-8


import unittest
from collections import namedtuple

import pytest
from mock import mock

from conans.cli.output import ConanOutput
from conans.errors import ConanException

# TODO: 2.0: add some unittests for the new cache on getting the fields that replace the metadata
from conans.model.recipe_ref import RecipeReference
from conans.test.utils.mocks import RedirectedTestOutput
from conans.test.utils.tools import redirect_output


class UpdateRevisionInMetadataTests(unittest.TestCase):

    def setUp(self):
        ref = RecipeReference.loads("lib/version@user/channel")
        # FIXME: 2.0: PackageCacheLayout does not exist anymore
        # self.package_layout = PackageCacheLayout(base_folder=temp_folder(), ref=ref,
        #                                          short_paths=False, no_lock=True)

    @pytest.mark.xfail(reason="cache2.0")
    def test_scm_warn_not_pristine(self):
        with mock.patch("conans.client.cmd.export._detect_scm_revision",
                        return_value=("revision", "git", False)):
            path = None
            digest = namedtuple("Digest", "summary_hash")
            output = RedirectedTestOutput()
            with redirect_output(output):
                _update_revision_in_metadata(self.package_layout, ConanOutput(), path, digest, "scm")
            self.assertIn("WARN: Repo status is not pristine: there might be modified files",
                          output.getvalue())

    @pytest.mark.xfail(reason="cache2.0")
    def test_scm_behavior(self):
        revision_mode = "scm"

        digest = None
        path = None
        with mock.patch("conans.client.cmd.export._detect_scm_revision",
                        return_value=("1234", "git", True)):
            output = RedirectedTestOutput()
            with redirect_output(output):
                rev = _update_revision_in_metadata(self.package_layout, ConanOutput(),
                                               path, digest, revision_mode)
        self.assertEqual(rev, "1234")
        self.assertIn("Using git commit as the recipe revision", output.getvalue())

    @pytest.mark.xfail(reason="cache2.0")
    def test_hash_behavior(self):
        revision_mode = "hash"

        digest = namedtuple("Digest", "summary_hash")
        digest.summary_hash = "1234"
        path = None
        rev = _update_revision_in_metadata(self.package_layout, self.output,
                                           path, digest, revision_mode)
        self.assertEqual(rev, "1234")
        self.assertIn("Using the exported files summary hash as the recipe revision", self.output)

    @pytest.mark.xfail(reason="cache2.0")
    def test_invalid_behavior(self):
        revision_mode = "auto"
        digest = path = None

        with self.assertRaisesRegex(ConanException, "Revision mode should be"):
            _update_revision_in_metadata(self.package_layout, self.output,
                                           path, digest, revision_mode)
