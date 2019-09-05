# coding=utf-8

import os
import platform
import unittest

import six
from mock import Mock, patch
from parameterized import parameterized

from conans.client.cache.cache import ClientCache
from conans.client.conf import default_client_conf, ConanClientConfigParser
from conans.client.rest.conan_requester import ConanRequester, HTTPAdapter, SSLContextAdapter
from conans.client.tools import environment_append
from conans.client.tools.files import replace_in_file, save
from conans.errors import ConanException
from conans.paths import CACERT_FILE
from conans.test.utils.tools import TestBufferConanOutput, temp_folder
from conans.util.files import normalize


class MockRequesterGet(Mock):
    verify = None
    adapters = {}

    def get(self, _, **kwargs):
        self.verify = kwargs.get('verify', None)

    def mount(self, prefix, adapter):
        self.adapters[prefix] = adapter


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
        save(conan_conf, normalize(default_client_conf))
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


class ConanRequesterSystemCerts(unittest.TestCase):

    @patch("requests.Session", return_value=MockRequesterGet())
    def test_default(self, mock):
        cache = ClientCache(temp_folder(), TestBufferConanOutput())
        ConanRequester(cache.config)

        mocked_session = mock.return_value
        self.assertEqual(type(mocked_session.adapters["http://"]), HTTPAdapter)
        self.assertEqual(type(mocked_session.adapters["https://"]), HTTPAdapter)

    @parameterized.expand([("1", ), ("True", ), ("true", )])
    @patch("requests.Session", return_value=MockRequesterGet())
    def test_activate_environment(self, env_value, mock):
        with environment_append({"CONAN_USE_SYSTEM_CERTS": env_value}):
            cache = ClientCache(temp_folder(), TestBufferConanOutput())

            try:
                ConanRequester(cache.config)
            except ConanException as e:
                # Some 'requests' versions running in MacOS doesn't support this feature, see
                #   https://github.com/conan-io/conan/pull/5659#issuecomment-528262969
                self.assertEqual(platform.system(), "Darwin")
                self.assertIn("The system SSL cert storage cannot be used", str(e))
            else:
                mocked_session = mock.return_value
                self.assertEqual(type(mocked_session.adapters["http://"]), HTTPAdapter)
                self.assertEqual(type(mocked_session.adapters["https://"]), SSLContextAdapter)

    @patch("requests.Session", return_value=MockRequesterGet())
    def test_activate_cli(self, mock):
        output = TestBufferConanOutput()
        cache = ClientCache(temp_folder(), output)
        replace_in_file(cache.conan_conf_path, "[general]",
                        "[general]\nuse_system_certs=True", output=output)
        cache._config = None  # Force reading conan.conf again
        try:
            ConanRequester(cache.config)
        except ConanException as e:
            # Some 'requests' versions running in MacOS doesn't support this feature, see
            #   https://github.com/conan-io/conan/pull/5659#issuecomment-528262969
            self.assertEqual(platform.system(), "Darwin")
            self.assertIn("The system SSL cert storage cannot be used", str(e))
        else:
            mocked_session = mock.return_value
            self.assertEqual(type(mocked_session.adapters["http://"]), HTTPAdapter)
            self.assertEqual(type(mocked_session.adapters["https://"]), SSLContextAdapter)

    @parameterized.expand([("0", ), ("False", ), ("false", ), ("any-other-thing", )])
    @patch("requests.Session", return_value=MockRequesterGet())
    def test_deactivate_environment(self, env_value, mock):
        with environment_append({"CONAN_USE_SYSTEM_CERTS": env_value}):
            cache = ClientCache(temp_folder(), TestBufferConanOutput())
            ConanRequester(cache.config)

            mocked_session = mock.return_value
            self.assertEqual(type(mocked_session.adapters["http://"]), HTTPAdapter)
            self.assertEqual(type(mocked_session.adapters["https://"]), HTTPAdapter)
