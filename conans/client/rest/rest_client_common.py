import json

from requests.auth import AuthBase, HTTPBasicAuth

from conans import COMPLEX_SEARCH_CAPABILITY
from conans.errors import (EXCEPTION_CODE_MAPPING, NotFoundException, ConanException,
                           AuthenticationException, RecipeNotFoundException,
                           PackageNotFoundException)
from conans.model.ref import ConanFileReference
from conans.search.search import filter_packages
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


def _base_error(error_code):
    return int(str(error_code)[0] + "00")


def get_exception_from_error(error_code):
    try:
        tmp = {}
        for key, value in EXCEPTION_CODE_MAPPING.items():
            if key not in (RecipeNotFoundException, PackageNotFoundException):
                tmp[value] = key
        if error_code in tmp:
            logger.debug("REST ERROR: %s" % str(tmp[error_code]))
            return tmp[error_code]
        else:
            logger.debug("REST ERROR: %s" % str(_base_error(error_code)))
            return tmp[_base_error(error_code)]
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

    def __init__(self, remote_url, token, custom_headers, output, requester, verify_ssl,
                 put_headers=None):

        self.token = token
        self.remote_url = remote_url
        self.custom_headers = custom_headers
        self._output = output
        self.requester = requester
        self.verify_ssl = verify_ssl
        self._put_headers = put_headers

    @property
    def auth(self):
        return JWTAuth(self.token)

    @handle_return_deserializer()
    def authenticate(self, user, password):
        """Sends user + password to get a token"""
        auth = HTTPBasicAuth(user, password)
        url = self.router.common_authenticate()
        logger.debug("REST: Authenticate: %s" % url)
        ret = self.requester.get(url, auth=auth, headers=self.custom_headers,
                                 verify=self.verify_ssl)
        if ret.status_code == 401:
            raise AuthenticationException("Wrong user or password")
        # Cannot check content-type=text/html, conan server is doing it wrong
        if not ret.ok or "html>" in str(ret.content):
            raise ConanException("%s\n\nInvalid server response, check remote URL and "
                                 "try again" % str(ret.content))
        return ret

    @handle_return_deserializer()
    def check_credentials(self):
        """If token is not valid will raise AuthenticationException.
        User will be asked for new user/pass"""
        url = self.router.common_check_credentials()
        logger.debug("REST: Check credentials: %s" % url)
        ret = self.requester.get(url, auth=self.auth, headers=self.custom_headers,
                                 verify=self.verify_ssl)
        return ret

    def server_info(self):
        """Get information about the server: status, version, type and capabilities"""
        url = self.router.ping()
        logger.debug("REST: ping: %s" % url)

        ret = self.requester.get(url, auth=self.auth, headers=self.custom_headers,
                                 verify=self.verify_ssl)
        if ret.status_code == 404:
            raise NotFoundException("Not implemented endpoint")

        version_check = ret.headers.get('X-Conan-Client-Version-Check', None)
        server_version = ret.headers.get('X-Conan-Server-Version', None)
        server_capabilities = ret.headers.get('X-Conan-Server-Capabilities', "")
        server_capabilities = [cap.strip() for cap in server_capabilities.split(",") if cap]

        return version_check, server_version, server_capabilities

    def get_json(self, url, data=None):
        headers = self.custom_headers
        if data:  # POST request
            headers.update({'Content-type': 'application/json',
                            'Accept': 'text/plain',
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
            raise get_exception_from_error(response.status_code)(response.text)

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

        if not query:
            url = self.router.search_packages(ref)
            package_infos = self.get_json(url)
            return package_infos

        # Read capabilities
        try:
            _, _, capabilities = self.server_info()
        except NotFoundException:
            capabilities = []

        if COMPLEX_SEARCH_CAPABILITY in capabilities:
            url = self.router.search_packages(ref, query)
            package_infos = self.get_json(url)
            return package_infos
        else:
            url = self.router.search_packages(ref)
            package_infos = self.get_json(url)
            return filter_packages(query, package_infos)

    def _post_json(self, url, payload):
        logger.debug("REST: post: %s" % url)
        response = self.requester.post(url,
                                       auth=self.auth,
                                       headers=self.custom_headers,
                                       verify=self.verify_ssl,
                                       json=payload)
        return response
