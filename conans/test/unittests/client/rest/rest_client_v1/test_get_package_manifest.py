# coding=utf-8

import unittest
from collections import namedtuple

from mock import patch

from conans.client.rest.rest_client_v1 import RestV1Methods
from conans.errors import ConanException
from conans.model.ref import PackageReference
from conans.paths import CONAN_MANIFEST


class GetPackageManifestTestCase(unittest.TestCase):

    def test_corrupted_manifest(self):
        remote_url = "http://some.url"
        pref = PackageReference.loads("lib/version@user/channel#rrev:123#prev")
        returned_files = {CONAN_MANIFEST: b"not expected content"}

        with patch.object(RestV1Methods, "_get_file_to_url_dict", return_value=None), \
             patch.object(RestV1Methods, "_download_files", return_value=returned_files):

            config = namedtuple("ConfigMock", "download_cache")(None)
            v1 = RestV1Methods(remote_url, token=None, custom_headers=None, output=None,
                               requester=None, config=config, verify_ssl=None)
            with self.assertRaises(ConanException) as exc:
                v1.get_package_manifest(pref=pref)

            # Exception tells me about the originating error and the request I was doing.
            # It doesn't show the PREV because it is v1
            self.assertIn("Error retrieving manifest file for package '{}'"
                          " from remote ({})".format(pref, remote_url),
                          str(exc.exception))
            self.assertIn("invalid literal for int() with base 10", str(exc.exception))
