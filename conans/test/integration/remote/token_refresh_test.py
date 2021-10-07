import unittest
from collections import namedtuple

from mock import Mock

from conans.client.cache.remote_registry import Remote
from conans.client.rest.auth_manager import ConanApiAuthManager
from conans.client.rest.rest_client import RestApiClientFactory
from conans.model.ref import ConanFileReference
from conans.test.utils.mocks import LocalDBMock, TestBufferConanOutput
from conans.client.userio import UserIO


common_headers = {"X-Conan-Server-Capabilities": "oauth_token", "Content-Type": "application/json"}


class ResponseOK(object):
    def __init__(self):
        self.ok = True
        self.headers = common_headers
        self.status_code = 200
        self.content = b''


class ResponseDownloadURLs(object):
    def __init__(self):
        self.ok = True
        self.headers = common_headers
        self.status_code = 200
        self.content = b'{}'


class ResponseWithTokenMock(object):
    def __init__(self, token):
        self.token = token
        self.ok = True
        self.headers = common_headers
        self.status_code = 200
        self.content = ''

    def json(self):
        return {"access_token": self.token, "refresh_token": "refresh_token"}


class ResponseAuthenticationRequired(object):
    def __init__(self):
        self.ok = False
        self.headers = common_headers
        self.status_code = 401
        self.content = b'Login needed'


class RequesterWithTokenMock(object):

    def get(self, url, **kwargs):
        if not kwargs["auth"].token or kwargs["auth"].token == "expired":
            return ResponseAuthenticationRequired()
        if url.endswith("download_urls"):
            return ResponseDownloadURLs()
        elif url.endswith("users/authenticate"):
            raise Exception("This endpoint should't be called when oauth supported")

    def post(self, url, **kwargs):
        """If the call is to refresh we return "refreshed_access_token" otherwise we return
        "access_token"
        """
        if url.endswith("users/token"):
            if kwargs.get("data") and kwargs.get("data").get("grant_type") == "refresh_token":
                return ResponseWithTokenMock("refreshed_access_token")
            return ResponseWithTokenMock("access_token")
        else:
            raise Exception("This endpoint should't be reached")


class TestTokenRefresh(unittest.TestCase):

    def setUp(self):
        mocked_user_io = UserIO(out=TestBufferConanOutput())
        mocked_user_io.get_username = Mock(return_value="myuser")
        mocked_user_io.get_password = Mock(return_value="mypassword")

        requester = RequesterWithTokenMock()
        config = namedtuple("ConfigMock", "revisions_enabled download_cache retry retry_wait")\
            (False, None, None, None)
        self.rest_client_factory = RestApiClientFactory(mocked_user_io.out,
                                                        requester, config=config,
                                                        artifacts_properties=None)
        self.localdb = LocalDBMock()
        self.auth_manager = ConanApiAuthManager(self.rest_client_factory, mocked_user_io,
                                                self.localdb)
        self.remote = Remote("myremote", "myurl", True, True)
        self.ref = ConanFileReference.loads("lib/1.0@conan/stable")

    def test_auth_with_token(self):
        """Test that if the capability is there, then we use the new endpoint"""
        self.auth_manager.call_rest_api_method(self.remote, "get_recipe", self.ref, ".")
        self.assertEqual(self.localdb.user, "myuser")
        self.assertEqual(self.localdb.access_token, "access_token")
        self.assertEqual(self.localdb.refresh_token, "refresh_token")

    def test_refresh_with_token(self):
        """The mock will raise 401 for a token value "expired" so it will try to refresh
        and only if the refresh endpoint is called, the value will be "refreshed_access_token"
        """
        self.localdb.access_token = "expired"
        self.localdb.refresh_token = "refresh_token"

        self.auth_manager.call_rest_api_method(self.remote, "get_recipe", self.ref, ".")
        self.assertEqual(self.localdb.user, "myuser")
        self.assertEqual(self.localdb.access_token, "refreshed_access_token")
        self.assertEqual(self.localdb.refresh_token, "refresh_token")
