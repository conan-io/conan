# coding=utf-8


import unittest

from mock import patch

from conans.client.rest.client_routes import ClientV2Router
from conans.client.rest.rest_client_v2 import RestV2Methods
from conans.errors import ConanException
from conans.model.ref import PackageReference


class GetPackageManifestTestCase(unittest.TestCase):

    def test_corrupted_manifest(self):
        remote_url = "http://some.url"
        pref = PackageReference.loads("lib/version@user/channel:123#packageid")

        with patch.object(RestV2Methods, "_get_remote_file_contents", return_value=b"fail"), \
             patch.object(ClientV2Router, "package_manifest", return_value=None):

            v2 = RestV2Methods(remote_url, token=None, custom_headers=None, output=None,
                               requester=None, config=None, verify_ssl=None)
            with self.assertRaises(ConanException) as exc:
                v2.get_package_manifest(pref=pref)

            # Exception tells me about the originating error and the request I was doing.
            self.assertIn("Error retrieving manifest file for package '{}'"
                          " from remote ({})".format(pref.full_str(), remote_url),
                          str(exc.exception))
            self.assertIn("invalid literal for int() with base 10", str(exc.exception))
