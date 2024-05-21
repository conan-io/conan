import unittest

import mock

from conan.api.model import Remote
from conans.client.rest.auth_manager import ConanApiAuthManager
from conans.client.rest.rest_client import RestApiClientFactory
from conans.model.conf import ConfDefinition
from conans.model.recipe_ref import RecipeReference
from conan.test.utils.mocks import LocalDBMock
from conan.test.utils.test_files import temp_folder

common_headers = {"X-Conan-Server-Capabilities": "oauth_token,revisions",
                  "Content-Type": "application/json"}


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
        self.content = b'{"files": {}}'


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
        if url.endswith("files"):
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
    # MISSING MOCKS

    def setUp(self):
        requester = RequesterWithTokenMock()
        config = ConfDefinition()
        self.rest_client_factory = RestApiClientFactory(requester, config=config)
        self.localdb = LocalDBMock()
        self.auth_manager = ConanApiAuthManager(self.rest_client_factory, temp_folder(), self.localdb, config)
        self.remote = Remote("myremote", "myurl", True, True)
        self.ref = RecipeReference.loads("lib/1.0@conan/stable#myreciperev")

    def test_auth_with_token(self):
        """Test that if the capability is there, then we use the new endpoint"""
        with mock.patch("conans.client.rest.remote_credentials.UserInput.request_login",
                        return_value=("myuser", "mypassword")):

            self.auth_manager.call_rest_api_method(self.remote, "get_recipe", self.ref, ".",
                                                   metadata=None, only_metadata=False)
            self.assertEqual(self.localdb.user, "myuser")
            self.assertEqual(self.localdb.access_token, "access_token")
            self.assertEqual(self.localdb.refresh_token, "refresh_token")

    def test_refresh_with_token(self):
        """The mock will raise 401 for a token value "expired" so it will try to refresh
        and only if the refresh endpoint is called, the value will be "refreshed_access_token"
        """
        with mock.patch("conans.client.rest.remote_credentials.UserInput.request_login",
                        return_value=("myuser", "mypassword")):
            self.localdb.access_token = "expired"
            self.localdb.refresh_token = "refresh_token"

            self.auth_manager.call_rest_api_method(self.remote, "get_recipe", self.ref, ".",
                                                   metadata=None, only_metadata=False)
            self.assertEqual(self.localdb.user, "myuser")
            self.assertEqual(self.localdb.access_token, "refreshed_access_token")
            self.assertEqual(self.localdb.refresh_token, "refresh_token")
