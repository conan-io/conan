import json

from requests.auth import AuthBase, HTTPBasicAuth

from conans.client.rest import response_to_str
from conans.errors import (EXCEPTION_CODE_MAPPING, ConanException,
                           AuthenticationException, RecipeNotFoundException,
                           PackageNotFoundException)
from conans.model.recipe_ref import RecipeReference


class JWTAuth(AuthBase):
    """Attaches JWT Authentication to the given Request object."""

    def __init__(self, token):
        self.token = token

    def __call__(self, request):
        if self.token:
            request.headers['Authorization'] = "Bearer %s" % str(self.token)
        return request


def get_exception_from_error(error_code):
    tmp = {v: k for k, v in EXCEPTION_CODE_MAPPING.items()  # All except NotFound
           if k not in (RecipeNotFoundException, PackageNotFoundException)}
    if error_code in tmp:
        # logger.debug("REST ERROR: %s" % str(tmp[error_code]))
        return tmp[error_code]
    else:
        base_error = int(str(error_code)[0] + "00")
        # logger.debug("REST ERROR: %s" % str(base_error))
        try:
            return tmp[base_error]
        except KeyError:
            return None


class RestCommonMethods(object):

    def __init__(self, remote_url, token, custom_headers, requester, config, verify_ssl):
        self.token = token
        self.remote_url = remote_url
        self.custom_headers = custom_headers
        self.requester = requester
        self._config = config
        self.verify_ssl = verify_ssl

    @property
    def auth(self):
        return JWTAuth(self.token)

    @staticmethod
    def _check_error_response(ret):
        if ret.status_code == 401:
            raise AuthenticationException("Wrong user or password")
        # Cannot check content-type=text/html, conan server is doing it wrong
        if not ret.ok or "html>" in str(ret.content):
            raise ConanException("%s\n\nInvalid server response, check remote URL and "
                                 "try again" % str(ret.content))

    def authenticate(self, user, password):
        """Sends user + password to get:
          - A plain response with a regular token (not supported refresh in the remote) and None
        """
        auth = HTTPBasicAuth(user, password)
        url = self.router.common_authenticate()
        # logger.debug("REST: Authenticate to get access_token: %s" % url)
        ret = self.requester.get(url, auth=auth, headers=self.custom_headers,
                                 verify=self.verify_ssl)

        self._check_error_response(ret)
        return ret.content.decode()

    def authenticate_oauth(self, user, password):
        """Sends user + password to get:
            - A json with an access_token and a refresh token (if supported in the remote)
                    Artifactory >= 6.13.X
        """
        url = self.router.oauth_authenticate()
        auth = HTTPBasicAuth(user, password)
        headers = {}
        headers.update(self.custom_headers)
        headers["Content-type"] = "application/x-www-form-urlencoded"
        # logger.debug("REST: Authenticating with OAUTH: %s" % url)
        ret = self.requester.post(url, auth=auth, headers=headers, verify=self.verify_ssl)
        self._check_error_response(ret)

        data = ret.json()
        access_token = data["access_token"]
        refresh_token = data["refresh_token"]
        # logger.debug("REST: Obtained refresh and access tokens")
        return access_token, refresh_token

    def refresh_token(self, token, refresh_token):
        """Sends access_token and the refresh_token to get a pair of
        access_token and refresh token

        Artifactory >= 6.13.X
        """
        url = self.router.oauth_authenticate()
        # logger.debug("REST: Refreshing Token: %s" % url)
        headers = {}
        headers.update(self.custom_headers)
        headers["Content-type"] = "application/x-www-form-urlencoded"
        payload = {'access_token': token, 'refresh_token': refresh_token,
                   'grant_type': 'refresh_token'}
        ret = self.requester.post(url, headers=headers, verify=self.verify_ssl, data=payload)
        self._check_error_response(ret)

        data = ret.json()
        if "access_token" not in data:
            # logger.debug("REST: unexpected data from server: {}".format(data))
            raise ConanException("Error refreshing the token")

        new_access_token = data["access_token"]
        new_refresh_token = data["refresh_token"]
        # logger.debug("REST: Obtained new refresh and access tokens")
        return new_access_token, new_refresh_token

    def check_credentials(self):
        """If token is not valid will raise AuthenticationException.
        User will be asked for new user/pass"""
        url = self.router.common_check_credentials()
        # logger.debug("REST: Check credentials: %s" % url)
        ret = self.requester.get(url, auth=self.auth, headers=self.custom_headers,
                                 verify=self.verify_ssl)
        if ret.status_code != 200:
            ret.charset = "utf-8"  # To be able to access ret.text (ret.content are bytes)
            text = ret.text if ret.status_code != 404 else "404 Not found"
            raise get_exception_from_error(ret.status_code)(text)
        return ret.content.decode()

    def server_capabilities(self, user=None, password=None):
        """Get information about the server: status, version, type and capabilities"""
        url = self.router.ping()
        # logger.debug("REST: ping: %s" % url)
        if user and password:
            # This can happen in "conan remote login" cmd. Instead of empty token, use HttpBasic
            auth = HTTPBasicAuth(user, password)
        else:
            auth = self.auth
        ret = self.requester.get(url, auth=auth, headers=self.custom_headers, verify=self.verify_ssl)

        server_capabilities = ret.headers.get('X-Conan-Server-Capabilities')
        if not server_capabilities and not ret.ok:
            # Old Artifactory might return 401/403 without capabilities, we don't want
            # to cache them #5687, so raise the exception and force authentication
            raise get_exception_from_error(ret.status_code)(response_to_str(ret))
        if server_capabilities is None:
            # Some servers returning 200-ok, even if not valid repo
            raise ConanException(f"Remote {self.remote_url} doesn't seem like a valid Conan remote")

        return [cap.strip() for cap in server_capabilities.split(",") if cap]

    def get_json(self, url, data=None, headers=None):
        req_headers = self.custom_headers.copy()
        req_headers.update(headers or {})
        if data:  # POST request
            req_headers.update({'Content-type': 'application/json',
                                'Accept': 'application/json'})
            # logger.debug("REST: post: %s" % url)
            response = self.requester.post(url, auth=self.auth, headers=req_headers,
                                           verify=self.verify_ssl,
                                           stream=True,
                                           data=json.dumps(data))
        else:
            # logger.debug("REST: get: %s" % url)
            response = self.requester.get(url, auth=self.auth, headers=req_headers,
                                          verify=self.verify_ssl,
                                          stream=True)

        if response.status_code != 200:  # Error message is text
            response.charset = "utf-8"  # To be able to access ret.text (ret.content are bytes)
            raise get_exception_from_error(response.status_code)(response_to_str(response))

        content = response.content.decode()
        content_type = response.headers.get("Content-Type")
        if content_type != 'application/json' and content_type != 'application/json; charset=utf-8':
            raise ConanException("%s\n\nResponse from remote is not json, but '%s'"
                                 % (content, content_type))

        try:  # This can fail, if some proxy returns 200 and an html message
            result = json.loads(content)
        except Exception:
            raise ConanException("Remote responded with broken json: %s" % content)
        if not isinstance(result, dict):
            raise ConanException("Unexpected server response %s" % result)
        return result

    def upload_recipe(self, ref, files_to_upload):
        if files_to_upload:
            self._upload_recipe(ref, files_to_upload)

    def upload_package(self, pref, files_to_upload):
        self._upload_package(pref, files_to_upload)

    def search(self, pattern=None, ignorecase=True):
        """
        the_files: dict with relative_path: content
        """
        url = self.router.search(pattern, ignorecase)
        response = self.get_json(url)["results"]
        # We need to filter the "_/_" user and channel from Artifactory
        ret = []
        for reference in response:
            try:
                ref = RecipeReference.loads(reference)
            except TypeError as te:
                raise ConanException("Unexpected response from server.\n"
                                     "URL: `{}`\n"
                                     "Expected an iterable, but got {}.".format(url, type(response)))
            if ref.user == "_":
                ref.user = None
            if ref.channel == "_":
                ref.channel = None
            ret.append(ref)
        return ret

    def search_packages(self, ref):
        """Client is filtering by the query"""
        url = self.router.search_packages(ref)
        package_infos = self.get_json(url)
        return package_infos
