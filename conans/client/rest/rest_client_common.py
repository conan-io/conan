import json

import time
from requests.auth import AuthBase, HTTPBasicAuth
from six.moves.urllib.parse import urlencode

from conans import COMPLEX_SEARCH_CAPABILITY
from conans.client.cmd.uploader import UPLOAD_POLICY_NO_OVERWRITE, \
    UPLOAD_POLICY_NO_OVERWRITE_RECIPE, UPLOAD_POLICY_FORCE
from conans.errors import (EXCEPTION_CODE_MAPPING, NotFoundException, ConanException,
                           AuthenticationException)
from conans.model.manifest import FileTreeManifest
from conans.model.ref import ConanFileReference
from conans.search.search import filter_packages
from conans.util.files import decode_text, load
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
        tmp = {value: key for key, value in EXCEPTION_CODE_MAPPING.items()}
        if error_code in tmp:
            logger.debug("From server: %s" % str(tmp[error_code]))
            return tmp[error_code]
        else:
            logger.debug("From server: %s" % str(_base_error(error_code)))
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
        url = "%s/users/authenticate" % self.remote_api_url
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
        url = "%s/users/check_credentials" % self.remote_api_url
        ret = self.requester.get(url, auth=self.auth, headers=self.custom_headers,
                                 verify=self.verify_ssl)
        return ret

    def server_info(self):
        """Get information about the server: status, version, type and capabilities"""
        url = "%s/ping" % self.remote_api_url
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
            response = self.requester.post(url, auth=self.auth, headers=headers,
                                           verify=self.verify_ssl,
                                           stream=True,
                                           data=json.dumps(data))
        else:
            response = self.requester.get(url, auth=self.auth, headers=headers,
                                          verify=self.verify_ssl,
                                          stream=True)

        if response.status_code != 200:  # Error message is text
            response.charset = "utf-8"  # To be able to access ret.text (ret.content are bytes)
            raise get_exception_from_error(response.status_code)(response.text)

        result = json.loads(decode_text(response.content))
        if not isinstance(result, dict):
            raise ConanException("Unexpected server response %s" % result)
        return result

    def upload_recipe(self, conan_reference, the_files, retry, retry_wait, policy,
                      remote_manifest):
        """
        the_files: dict with relative_path: content
        """
        self.check_credentials()

        # Get the remote snapshot
        remote_snapshot, conan_reference = self._get_recipe_snapshot(conan_reference)

        if remote_snapshot and policy != UPLOAD_POLICY_FORCE:
            remote_manifest = remote_manifest or self.get_conan_manifest(conan_reference)
            local_manifest = FileTreeManifest.loads(load(the_files["conanmanifest.txt"]))

            if remote_manifest == local_manifest:
                return False, conan_reference

            if policy in (UPLOAD_POLICY_NO_OVERWRITE, UPLOAD_POLICY_NO_OVERWRITE_RECIPE):
                raise ConanException("Local recipe is different from the remote recipe. "
                                     "Forbidden overwrite")

        files_to_upload = {filename.replace("\\", "/"): path
                           for filename, path in the_files.items()}
        deleted = set(remote_snapshot).difference(the_files)

        if files_to_upload:
            self._upload_recipe(conan_reference, files_to_upload, retry, retry_wait)
        if deleted:
            self._remove_conanfile_files(conan_reference, deleted)

        return (files_to_upload or deleted), conan_reference

    def upload_package(self, package_reference, the_files, retry, retry_wait, policy):
        """
        basedir: Base directory with the files to upload (for read the files in disk)
        relative_files: relative paths to upload
        """
        self.check_credentials()

        t1 = time.time()
        # Get the remote snapshot
        remote_snapshot, package_reference = self._get_package_snapshot(package_reference)
        if remote_snapshot:
            remote_manifest = self.get_package_manifest(package_reference)
            local_manifest = FileTreeManifest.loads(load(the_files["conanmanifest.txt"]))

            if remote_manifest == local_manifest:
                return False

            if policy == UPLOAD_POLICY_NO_OVERWRITE:
                raise ConanException("Local package is different from the remote package. "
                                     "Forbidden overwrite")

        files_to_upload = the_files
        deleted = set(remote_snapshot).difference(the_files)
        if files_to_upload:
            self._upload_package(package_reference, files_to_upload, retry, retry_wait)
        if deleted:
            raise Exception("This shouldn't be happening, deleted files "
                            "in local package present in remote: %s.\n Please, report it at "
                            "https://github.com/conan-io/conan/issues " % str(deleted))

        logger.debug("====> Time rest client upload_package: %f" % (time.time() - t1))
        return files_to_upload or deleted

    def search(self, pattern=None, ignorecase=True):
        """
        the_files: dict with relative_path: content
        """
        query = ''
        if pattern:
            params = {"q": pattern}
            if not ignorecase:
                params["ignorecase"] = "False"
            query = "?%s" % urlencode(params)

        url = "%s/conans/search%s" % (self.remote_api_url, query)
        response = self.get_json(url)["results"]
        return [ConanFileReference.loads(ref) for ref in response]

    def search_packages(self, reference, query):
        url = "%s/search?" % self._recipe_url(reference)

        if not query:
            package_infos = self.get_json(url)
            return package_infos

        # Read capabilities
        try:
            _, _, capabilities = self.server_info()
        except NotFoundException:
            capabilities = []

        if COMPLEX_SEARCH_CAPABILITY in capabilities:
            url += urlencode({"q": query})
            package_infos = self.get_json(url)
            return package_infos
        else:
            package_infos = self.get_json(url)
            return filter_packages(query, package_infos)

    @handle_return_deserializer()
    def remove_conanfile(self, conan_reference):
        """ Remove a recipe and packages """
        self.check_credentials()
        url = self._recipe_url(conan_reference)
        response = self.requester.delete(url,
                                         auth=self.auth,
                                         headers=self.custom_headers,
                                         verify=self.verify_ssl)
        return response

    @handle_return_deserializer()
    def remove_packages(self, conan_reference, package_ids=None):
        """ Remove any packages specified by package_ids"""
        self.check_credentials()
        payload = {"package_ids": package_ids}
        url = self._recipe_url(conan_reference) + "/packages/delete"
        return self._post_json(url, payload)

    @handle_return_deserializer()
    def _remove_conanfile_files(self, conan_reference, files):
        """ Remove recipe files """
        self.check_credentials()
        payload = {"files": [filename.replace("\\", "/") for filename in files]}
        url = self._recipe_url(conan_reference) + "/remove_files"
        return self._post_json(url, payload)

    def _post_json(self, url, payload):
        response = self.requester.post(url,
                                       auth=self.auth,
                                       headers=self.custom_headers,
                                       verify=self.verify_ssl,
                                       json=payload)
        return response

