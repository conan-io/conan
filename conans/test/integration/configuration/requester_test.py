# coding=utf-8

import os
import unittest

import mock
from mock import Mock, MagicMock

from conans import __version__
from conans.client.cache.cache import ClientCache
from conans.client.rest.conan_requester import ConanRequester
from conans.model.conf import ConfDefinition
from conans.test.utils.tools import temp_folder
from conans.util.files import save


class MockRequesterGet(Mock):
    verify = None

    def get(self, _, **kwargs):
        self.verify = kwargs.get('verify', None)


class ConanRequesterCacertPathTests(unittest.TestCase):

    @staticmethod
    def _create_requesters(cache_folder=None):
        cache = ClientCache(cache_folder or temp_folder())
        mock_requester = MockRequesterGet()
        requester = ConanRequester(cache.new_config)
        return requester, mock_requester, cache

    def test_default_no_verify(self):
        requester, mocked_requester, _ = self._create_requesters()
        with mock.patch("conans.client.rest.conan_requester.requests", mocked_requester):
            requester.get(url="aaa", verify=False)
            self.assertEqual(mocked_requester.verify, False)

    def test_default_verify(self):
        requester, mocked_requester, cache = self._create_requesters()
        with mock.patch("conans.client.rest.conan_requester.requests", mocked_requester):
            requester.get(url="aaa", verify=True)
            self.assertEqual(mocked_requester.verify, True)

    def test_cache_config(self):
        file_path = os.path.join(temp_folder(), "whatever_cacert")
        save(file_path, "")
        config = ConfDefinition()
        config.update("core.net.http:cacert_path", file_path)
        mocked_requester = MockRequesterGet()
        with mock.patch("conans.client.rest.conan_requester.requests", mocked_requester):
            requester = ConanRequester(config)
            requester.get(url="bbbb", verify=True)
        self.assertEqual(mocked_requester.verify, file_path)


class ConanRequesterHeadersTests(unittest.TestCase):
    def test_user_agent(self):
        cache_folder = temp_folder()
        cache = ClientCache(cache_folder)
        mock_http_requester = MagicMock()
        with mock.patch("conans.client.rest.conan_requester.requests", mock_http_requester):
            requester = ConanRequester(cache.new_config)
            requester.get(url="aaa")
            headers = mock_http_requester.get.call_args[1]["headers"]
            self.assertIn("Conan/%s" % __version__, headers["User-Agent"])

            requester.get(url="aaa", headers={"User-Agent": "MyUserAgent"})
            headers = mock_http_requester.get.call_args[1]["headers"]
            self.assertEqual("MyUserAgent", headers["User-Agent"])
