# coding=utf-8

import os
import unittest

import six
from mock import Mock

from conans.client.conan_api import Conan
from conans.client.tools import environment_append
from conans.client.tools.files import replace_in_file, save
from conans.errors import ConanException
from conans.paths import CACERT_FILE
from conans.test.utils.tools import TestBufferConanOutput, temp_folder
from conans.client.cache.cache import ClientCache


class MockRequesterGet(Mock):
    verify = None

    def get(self, url, **kwargs):
        self.verify = kwargs.get('verify', None)


class ConanRequesterCacertPathTests(unittest.TestCase):

    @staticmethod
    def _create_requesters(conan_user_home=None):
        conan_api = Conan(conan_user_home)
        cache = conan_api.cache
        conan_api.initialize()
        requester = conan_api._requester
        mock_requester = MockRequesterGet()
        requester._requester = mock_requester
        return requester, mock_requester, cache

    def test_default_no_verify(self):
        requester, mocked_requester, _ = self._create_requesters()
        requester.get(url="aaa", verify=False)
        self.assertEqual(mocked_requester.verify, False)

    def test_default_verify(self):
        requester, mocked_requester, cache = self._create_requesters()
        requester.get(url="aaa", verify=True)
        self.assertEqual(mocked_requester.verify, cache.cacert_path)

    def test_env_variable(self):
        file_path = os.path.join(temp_folder(), "whatever_cacert")
        save(file_path, "dummy content")
        with environment_append({"CONAN_CACERT_PATH": file_path}):
            requester, mocked_requester, _ = self._create_requesters()
            requester.get(url="aaa", verify=True)
            self.assertEqual(mocked_requester.verify, file_path)

    def test_cache_config(self):
        base_folder = temp_folder()
        file_path = os.path.join(base_folder, "whatever_cacert")
        save(file_path, "dummy")

        cache = ClientCache(base_folder, TestBufferConanOutput())
        replace_in_file(cache.conan_conf_path, "# cacert_path",
                        "cacert_path={}".format(file_path),
                        output=TestBufferConanOutput())

        requester, mocked_requester, _ = self._create_requesters(base_folder)

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
        self.assertEqual(mocked_requester.verify, cache.cacert_path)
        self.assertEqual(cache.cacert_path, default_cacert_path)
