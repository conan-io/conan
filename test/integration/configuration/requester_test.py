import os
import sys

import pytest
from unittest import mock
from unittest.mock import Mock, MagicMock

from conan import __version__
from conan.errors import ConanException
from conan.internal.rest.conan_requester import ConanRequester, _TrustStoreHTTPAdapter
from conan.internal.model.conf import ConfDefinition
from conan.test.utils.tools import temp_folder
from conan.internal.util.files import save


class MockRequesterGet(Mock):
    verify = None

    def get(self, _, **kwargs):
        self.verify = kwargs.get('verify', None)


class TestConanRequesterCacertPath:
    def test_default_no_verify(self):
        mocked_requester = MockRequesterGet()
        with mock.patch("conan.internal.rest.conan_requester.requests", mocked_requester):
            requester = ConanRequester(ConfDefinition())
            requester.get(url="aaa", verify=False)
            assert requester._http_requester.verify is False

    def test_default_verify(self):
        mocked_requester = MockRequesterGet()
        with mock.patch("conan.internal.rest.conan_requester.requests", mocked_requester):
            requester = ConanRequester(ConfDefinition())
            requester.get(url="aaa", verify=True)
            assert requester._http_requester.verify is True

    def test_cache_config(self):
        file_path = os.path.join(temp_folder(), "whatever_cacert")
        save(file_path, "")
        config = ConfDefinition()
        config.update("core.net.http:cacert_path", file_path)
        mocked_requester = MockRequesterGet()
        with mock.patch("conan.internal.rest.conan_requester.requests", mocked_requester):
            requester = ConanRequester(config)
            requester.get(url="bbbb", verify=True)
        assert requester._http_requester.verify == file_path


class TestConanRequesterTrustStore:
    def test_requires_python310(self):
        config = ConfDefinition()
        config.update("core.net.http:trust_store", True)
        with mock.patch("conan.internal.rest.conan_requester.requests", MagicMock()):
            with mock.patch("conan.internal.rest.conan_requester.sys.version_info", (3, 9, 0)):
                with pytest.raises(ConanException) as exc:
                    ConanRequester(config)
                assert "'core.net.http:trust_store' requires Python >= 3.10" in str(exc.value)

    def test_conflicts_with_cacert_path(self):
        file_path = os.path.join(temp_folder(), "whatever_cacert")
        save(file_path, "")
        config = ConfDefinition()
        config.update("core.net.http:trust_store", True)
        config.update("core.net.http:cacert_path", file_path)
        with mock.patch("conan.internal.rest.conan_requester.requests", MagicMock()):
            with mock.patch("conan.internal.rest.conan_requester.sys.version_info", (3, 11, 0)):
                with pytest.raises(ConanException) as exc:
                    ConanRequester(config)
                assert "core.net.http:trust_store" in str(exc.value)
                assert "core.net.http:cacert_path" in str(exc.value)

    def test_missing_package(self):
        config = ConfDefinition()
        config.update("core.net.http:trust_store", True)
        with mock.patch("conan.internal.rest.conan_requester.requests", MagicMock()):
            with mock.patch("conan.internal.rest.conan_requester.sys.version_info", (3, 11, 0)):
                with mock.patch.dict(sys.modules, {"truststore": None}):
                    with pytest.raises(ConanException) as exc:
                        ConanRequester(config)
                    assert "pip install truststore" in str(exc.value)

    @pytest.mark.skipif(sys.version_info < (3, 10), reason="truststore requires Python>=3.10")
    def test_happy_path(self):
        pytest.importorskip("truststore")
        config = ConfDefinition()
        config.update("core.net.http:trust_store", True)
        with mock.patch("conan.internal.rest.conan_requester.requests", MagicMock()):
            requester = ConanRequester(config)
        mount_calls = requester._http_requester.mount.call_args_list
        scheme, adapter = mount_calls[-1].args
        assert scheme == "https://"
        assert isinstance(adapter, _TrustStoreHTTPAdapter)


class TestConanRequesterHeaders:
    def test_user_agent(self):
        mock_http_requester = MagicMock()
        with mock.patch("conan.internal.rest.conan_requester.requests", mock_http_requester):
            requester = ConanRequester(ConfDefinition())
            requester.get(url="aaa")
            headers = requester._http_requester.get.call_args[1]["headers"]
            assert "Conan/%s" % __version__ in headers["User-Agent"]

            requester.get(url="aaa", headers={"User-Agent": "MyUserAgent"})
            headers = requester._http_requester.get.call_args[1]["headers"]
            assert "MyUserAgent" == headers["User-Agent"]
