# coding=utf-8


import unittest
from collections import namedtuple

import six
from mock import mock

from conans.client.cmd.export import _update_revision_in_metadata
from conans.model.ref import ConanFileReference
from conans.paths.package_layouts.package_cache_layout import PackageCacheLayout
from conans.test.utils.test_files import temp_folder
from conans.errors import ConanException
from conans.test.utils.mocks import TestBufferConanOutput


class UpdateRevisionInMetadataTests(unittest.TestCase):

    def setUp(self):
        ref = ConanFileReference.loads("lib/version@user/channel")
        self.package_layout = PackageCacheLayout(base_folder=temp_folder(), ref=ref,
                                                 short_paths=False, no_lock=True)
        self.output = TestBufferConanOutput()

    def test_scm_warn_not_pristine(self):
        with mock.patch("conans.client.cmd.export._detect_scm_revision",
                        return_value=("revision", "git", False)):
            path = None
            digest = namedtuple("Digest", "summary_hash")
            _update_revision_in_metadata(self.package_layout, True, self.output,
                                         path, digest, "scm")
            self.assertIn("WARN: Repo status is not pristine: there might be modified files",
                          self.output)

    def test_scm_behavior(self):
        revision_mode = "scm"

        digest = None
        path = None
        with mock.patch("conans.client.cmd.export._detect_scm_revision",
                        return_value=("1234", "git", True)):
            rev = _update_revision_in_metadata(self.package_layout, True, self.output,
                                               path, digest, revision_mode)
        self.assertEqual(rev, "1234")
        self.assertIn("Using git commit as the recipe revision", self.output)

    def test_hash_behavior(self):
        revision_mode = "hash"

        digest = namedtuple("Digest", "summary_hash")
        digest.summary_hash = "1234"
        path = None
        rev = _update_revision_in_metadata(self.package_layout, True, self.output,
                                           path, digest, revision_mode)
        self.assertEqual(rev, "1234")
        self.assertIn("Using the exported files summary hash as the recipe revision", self.output)

    def test_invalid_behavior(self):
        revision_mode = "auto"
        digest = path = None

        with six.assertRaisesRegex(self, ConanException, "Revision mode should be"):
            _update_revision_in_metadata(self.package_layout, True, self.output,
                                           path, digest, revision_mode)
