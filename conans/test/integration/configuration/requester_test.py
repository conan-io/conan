# coding=utf-8

import os
import unittest

import six
from mock import Mock, MagicMock

from conans import __version__
from conans.client.cache.cache import ClientCache
from conans.client.conf import get_default_client_conf, ConanClientConfigParser
from conans.client.rest.conan_requester import ConanRequester
from conans.client.tools import environment_append
from conans.client.tools.files import replace_in_file, save
from conans.errors import ConanException
from conans.paths import CACERT_FILE
from conans.test.utils.tools import temp_folder
from conans.test.utils.mocks import TestBufferConanOutput
from conans.util.files import normalize


class MockRequesterGet(Mock):
    verify = None

    def get(self, _, **kwargs):
        self.verify = kwargs.get('verify', None)


class ConanRequesterCacertPathTests(unittest.TestCase):

    @staticmethod
    def _create_requesters(cache_folder=None):
        cache = ClientCache(cache_folder or temp_folder(), TestBufferConanOutput())
        mock_requester = MockRequesterGet()
        requester = ConanRequester(cache.config, mock_requester)
        return requester, mock_requester, cache

    def test_default_no_verify(self):
        requester, mocked_requester, _ = self._create_requesters()
        requester.get(url="aaa", verify=False)
        self.assertEqual(mocked_requester.verify, False)

    def test_default_verify(self):
        requester, mocked_requester, cache = self._create_requesters()
        requester.get(url="aaa", verify=True)
        self.assertEqual(mocked_requester.verify, cache.config.cacert_path)

    def test_env_variable(self):
        file_path = os.path.join(temp_folder(), "whatever_cacert")
        save(file_path, "dummy content")
        with environment_append({"CONAN_CACERT_PATH": file_path}):
            requester, mocked_requester, _ = self._create_requesters()
            requester.get(url="aaa", verify=True)
            self.assertEqual(mocked_requester.verify, file_path)

    def test_cache_config(self):
        file_path = os.path.join(temp_folder(), "whatever_cacert")
        save(file_path, "")
        conan_conf = os.path.join(temp_folder(), "conan.conf")
        save(conan_conf, normalize(get_default_client_conf()))
        replace_in_file(conan_conf, "# cacert_path",
                        "cacert_path={}".format(file_path),
                        output=TestBufferConanOutput())
        config = ConanClientConfigParser(conan_conf)
        mocked_requester = MockRequesterGet()
        requester = ConanRequester(config, mocked_requester)
        requester.get(url="bbbb", verify=True)
        self.assertEqual(mocked_requester.verify, file_path)

    def test_non_existing_file(self):
        file_path = os.path.join(temp_folder(), "whatever_cacert")
        self.assertFalse(os.path.exists(file_path))
        with environment_append({"CONAN_CACERT_PATH": file_path}):
            with six.assertRaisesRegex(self, ConanException, "Configured file for 'cacert_path'"
                                                             " doesn't exist"):
                self._create_requesters()

    def test_non_existing_default_file(self):
        conan_user_home = temp_folder()
        default_cacert_path = os.path.join(conan_user_home, CACERT_FILE)
        self.assertFalse(os.path.exists(default_cacert_path))

        requester, mocked_requester, cache = self._create_requesters(conan_user_home)
        requester.get(url="aaa", verify=True)
        self.assertEqual(mocked_requester.verify, cache.config.cacert_path)
        self.assertEqual(cache.config.cacert_path, default_cacert_path)


class ConanRequesterHeadersTests(unittest.TestCase):
    def test_user_agent(self):
        cache_folder = temp_folder()
        cache = ClientCache(cache_folder, TestBufferConanOutput())
        mock_http_requester = MagicMock()
        requester = ConanRequester(cache.config, mock_http_requester)
        requester.get(url="aaa")
        headers = mock_http_requester.get.call_args[1]["headers"]
        self.assertIn("Conan/%s" % __version__, headers["User-Agent"])

        requester.get(url="aaa", headers={"User-Agent": "MyUserAgent"})
        headers = mock_http_requester.get.call_args[1]["headers"]
        self.assertEqual("MyUserAgent", headers["User-Agent"])
