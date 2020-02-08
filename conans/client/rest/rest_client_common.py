import json

from requests.auth import AuthBase, HTTPBasicAuth

from conans.client.rest import response_to_str
from conans.errors import (EXCEPTION_CODE_MAPPING, ConanException,
                           AuthenticationException, RecipeNotFoundException,
                           PackageNotFoundException)
from conans.model.ref import ConanFileReference
from conans.util.files import decode_text
from conans.util.log import logger


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
        logger.debug("REST ERROR: %s" % str(tmp[error_code]))
        return tmp[error_code]
    else:
        base_error = int(str(error_code)[0] + "00")
        logger.debug("REST ERROR: %s" % str(base_error))
        try:
            return tmp[base_error]
        except KeyError:
            return None


def handle_return_deserializer(deserializer=None):
    """Decorator for rest api methods.
    Map exceptions and http return codes and deserialize if needed.

    deserializer: Function for deserialize values"""
    def handle_return(method):
        def inner(*argc, **argv):
            ret = method(*argc, **argv)
            if ret.status_code != 200:
                ret.charset = "utf-8"  # To be able to access ret.text (ret.content are bytes)
                text = ret.text if ret.status_code != 404 else "404 Not found"
                raise get_exception_from_error(ret.status_code)(text)
            return deserializer(ret.content) if deserializer else decode_text(ret.content)
        return inner
    return handle_return


class RestCommonMethods(object):

    def __init__(self, remote_url, token, custom_headers, output, requester, config, verify_ssl,
                 artifacts_properties=None, matrix_params=False):
        self.token = token
        self.remote_url = remote_url
        self.custom_headers = custom_headers
        self._output = output
        self.requester = requester
        self._config = config
        self.verify_ssl = verify_ssl
        self._artifacts_properties = artifacts_properties
        self._matrix_params = matrix_params

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
        logger.debug("REST: Authenticate to get access_token: %s" % url)
        ret = self.requester.get(url, auth=auth, headers=self.custom_headers,
                                 verify=self.verify_ssl)

        self._check_error_response(ret)
        return decode_text(ret.content)

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
        logger.debug("REST: Authenticating with OAUTH: %s" % url)
        ret = self.requester.post(url, auth=auth, headers=headers, verify=self.verify_ssl)
        self._check_error_response(ret)

        data = ret.json()
        access_token = data["access_token"]
        refresh_token = data["refresh_token"]
        logger.debug("REST: Obtained refresh and access tokens")
        return access_token, refresh_token

    def refresh_token(self, token, refresh_token):
        """Sends access_token and the refresh_token to get a pair of
        access_token and refresh token

        Artifactory >= 6.13.X
        """
        url = self.router.oauth_authenticate()
        logger.debug("REST: Refreshing Token: %s" % url)
        headers = {}
        headers.update(self.custom_headers)
        headers["Content-type"] = "application/x-www-form-urlencoded"
        payload = {'access_token': token, 'refresh_token': refresh_token,
                   'grant_type': 'refresh_token'}
        ret = self.requester.post(url, headers=headers, verify=self.verify_ssl, data=payload)
        self._check_error_response(ret)

        data = ret.json()
        if "access_token" not in data:
            logger.debug("REST: unexpected data from server: {}".format(data))
            raise ConanException("Error refreshing the token")

        new_access_token = data["access_token"]
        new_refresh_token = data["refresh_token"]
        logger.debug("REST: Obtained new refresh and access tokens")
        return new_access_token, new_refresh_token

    @handle_return_deserializer()
    def check_credentials(self):
        """If token is not valid will raise AuthenticationException.
        User will be asked for new user/pass"""
        url = self.router.common_check_credentials()
        logger.debug("REST: Check credentials: %s" % url)
        ret = self.requester.get(url, auth=self.auth, headers=self.custom_headers,
                                 verify=self.verify_ssl)
        return ret

    def server_capabilities(self, user=None, password=None):
        """Get information about the server: status, version, type and capabilities"""
        url = self.router.ping()
        logger.debug("REST: ping: %s" % url)
        if user and password:
            # This can happen in "conan user" cmd. Instead of empty token, use HttpBasic
            auth = HTTPBasicAuth(user, password)
        else:
            auth = self.auth
        ret = self.requester.get(url, auth=auth, headers=self.custom_headers, verify=self.verify_ssl)

        server_capabilities = ret.headers.get('X-Conan-Server-Capabilities', "")
        if not server_capabilities and not ret.ok:
            # Old Artifactory might return 401/403 without capabilities, we don't want
            # to cache them #5687, so raise the exception and force authentication
            raise get_exception_from_error(ret.status_code)(response_to_str(ret))

        return [cap.strip() for cap in server_capabilities.split(",") if cap]

    def get_json(self, url, data=None):
        headers = self.custom_headers
        if data:  # POST request
            headers.update({'Content-type': 'application/json',
                            'Accept': 'application/json'})
            logger.debug("REST: post: %s" % url)
            response = self.requester.post(url, auth=self.auth, headers=headers,
                                           verify=self.verify_ssl,
                                           stream=True,
                                           data=json.dumps(data))
        else:
            logger.debug("REST: get: %s" % url)
            response = self.requester.get(url, auth=self.auth, headers=headers,
                                          verify=self.verify_ssl,
                                          stream=True)

        if response.status_code != 200:  # Error message is text
            response.charset = "utf-8"  # To be able to access ret.text (ret.content are bytes)
            raise get_exception_from_error(response.status_code)(response_to_str(response))

        content = decode_text(response.content)
        content_type = response.headers.get("Content-Type")
        if content_type != 'application/json':
            raise ConanException("%s\n\nResponse from remote is not json, but '%s'"
                                 % (content, content_type))

        try:  # This can fail, if some proxy returns 200 and an html message
            result = json.loads(content)
        except Exception:
            raise ConanException("Remote responded with broken json: %s" % content)
        if not isinstance(result, dict):
            raise ConanException("Unexpected server response %s" % result)
        return result

    def upload_recipe(self, ref, files_to_upload, deleted, retry, retry_wait):
        if files_to_upload:
            self._upload_recipe(ref, files_to_upload, retry, retry_wait)
        if deleted:
            self._remove_conanfile_files(ref, deleted)

    def get_recipe_snapshot(self, ref):
        # this method is used only for UPLOADING, then it requires the credentials
        # Check of credentials is done in the uploader
        url = self.router.recipe_snapshot(ref)
        snap = self._get_snapshot(url)
        return snap

    def get_package_snapshot(self, pref):
        # this method is also used to check the integrity of the package upstream
        # while installing, so check_credentials is done in uploader.
        url = self.router.package_snapshot(pref)
        snap = self._get_snapshot(url)
        return snap

    def upload_package(self, pref, files_to_upload, deleted, retry, retry_wait):
        if files_to_upload:
            self._upload_package(pref, files_to_upload, retry, retry_wait)
        if deleted:
            raise Exception("This shouldn't be happening, deleted files "
                            "in local package present in remote: %s.\n Please, report it at "
                            "https://github.com/conan-io/conan/issues " % str(deleted))

    def search(self, pattern=None, ignorecase=True):
        """
        the_files: dict with relative_path: content
        """
        url = self.router.search(pattern, ignorecase)
        response = self.get_json(url)["results"]
        return [ConanFileReference.loads(reference) for reference in response]

    def search_packages(self, ref, query):
        """Client is filtering by the query"""
        url = self.router.search_packages(ref, query)
        package_infos = self.get_json(url)
        return package_infos

