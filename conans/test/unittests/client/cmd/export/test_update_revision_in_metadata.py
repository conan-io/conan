# coding=utf-8


import unittest

from mock import mock

from conans.client.cmd.export import _update_revision_in_metadata
from conans.model.ref import ConanFileReference
from conans.paths.package_layouts.package_cache_layout import PackageCacheLayout
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestBufferConanOutput


class UpdateRevisionInMetadataTests(unittest.TestCase):

    def test_warn_not_pristine(self):
        output = TestBufferConanOutput()

        with mock.patch("conans.client.cmd.export._detect_scm_revision",
                        return_value=("revision", "git", False)):
            path = digest = None
            ref = ConanFileReference.loads("lib/version@user/channel")
            package_layout = PackageCacheLayout(base_folder=temp_folder(), ref=ref,
                                                short_paths=False, no_lock=True)
            _update_revision_in_metadata(package_layout, True, output, path, digest)
            self.assertIn("WARN: Repo status is not pristine: there might be modified files", output)
