import json

import time
from requests.auth import AuthBase, HTTPBasicAuth

from conans import COMPLEX_SEARCH_CAPABILITY, DEFAULT_REVISION_V1
from conans.client.cmd.uploader import UPLOAD_POLICY_NO_OVERWRITE, \
    UPLOAD_POLICY_NO_OVERWRITE_RECIPE, UPLOAD_POLICY_FORCE
from conans.client.rest.client_routes import ClientUsersRouterBuilder, \
    ClientSearchRouterBuilder, ClientBaseRouterBuilder
from conans.errors import (EXCEPTION_CODE_MAPPING, NotFoundException, ConanException,
                           AuthenticationException)
from conans.model.manifest import FileTreeManifest
from conans.model.ref import ConanFileReference, PackageReference
from conans.search.search import filter_packages
from conans.util.env_reader import get_env
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

    @property
    def users_router(self):
        return ClientUsersRouterBuilder(self.remote_api_url)

    @property
    def search_router(self):
        return ClientSearchRouterBuilder(self.remote_api_url)

    @property
    def base_router(self):
        return ClientBaseRouterBuilder(self.remote_api_url)

    @handle_return_deserializer()
    def authenticate(self, user, password):
        """Sends user + password to get a token"""
        auth = HTTPBasicAuth(user, password)
        url = self.users_router.common_authenticate()
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
        url = self.users_router.common_check_credentials()
        ret = self.requester.get(url, auth=self.auth, headers=self.custom_headers,
                                 verify=self.verify_ssl)
        return ret

    def server_info(self):
        """Get information about the server: status, version, type and capabilities"""
        url = self.base_router.ping()
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

        revisions_enabled = get_env("CONAN_CLIENT_REVISIONS_ENABLED", False)
        if not revisions_enabled and policy in (UPLOAD_POLICY_NO_OVERWRITE,
                                                UPLOAD_POLICY_NO_OVERWRITE_RECIPE):
            # Check if the latest revision is not the one we are uploading, with the compatibility
            # mode this is supposed to fail if someone tries to upload a different recipe
            latest_ref = conan_reference.copy_clear_rev()
            latest_snapshot, ref_latest_snapshot, _ = self._get_recipe_snapshot(latest_ref)
            server_with_revisions = ref_latest_snapshot.revision != DEFAULT_REVISION_V1
            if latest_snapshot and server_with_revisions and \
                    ref_latest_snapshot.revision != conan_reference.revision:
                raise ConanException("Local recipe is different from the remote recipe. "
                                     "Forbidden overwrite")

        # Get the remote snapshot
        remote_snapshot, ref_snapshot, rev_time = self._get_recipe_snapshot(conan_reference)

        if remote_snapshot and policy != UPLOAD_POLICY_FORCE:
            remote_manifest = remote_manifest or self.get_conan_manifest(ref_snapshot)
            local_manifest = FileTreeManifest.loads(load(the_files["conanmanifest.txt"]))

            if remote_manifest == local_manifest:
                return False, rev_time

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

        return (files_to_upload or deleted), rev_time

    def upload_package(self, package_reference, the_files, retry, retry_wait, policy):
        """
        basedir: Base directory with the files to upload (for read the files in disk)
        relative_files: relative paths to upload
        """
        self.check_credentials()

        revisions_enabled = get_env("CONAN_CLIENT_REVISIONS_ENABLED", False)
        if not revisions_enabled and policy == UPLOAD_POLICY_NO_OVERWRITE:
            # Check if the latest revision is not the one we are uploading, with the compatibility
            # mode this is supposed to fail if someone tries to upload a different recipe
            latest_pref = PackageReference(package_reference.conan, package_reference.package_id)
            latest_snapshot, ref_latest_snapshot, _ = self._get_package_snapshot(latest_pref)
            server_with_revisions = ref_latest_snapshot.revision != DEFAULT_REVISION_V1
            if latest_snapshot and server_with_revisions and \
                    ref_latest_snapshot.revision != package_reference.revision:
                raise ConanException("Local package is different from the remote package. "
                                     "Forbidden overwrite")
        t1 = time.time()
        # Get the remote snapshot
        pref = package_reference
        remote_snapshot, pref_snapshot, rev_time = self._get_package_snapshot(pref)

        if remote_snapshot:
            remote_manifest = self.get_package_manifest(pref_snapshot)
            local_manifest = FileTreeManifest.loads(load(the_files["conanmanifest.txt"]))

            if remote_manifest == local_manifest:
                return False, pref_snapshot, rev_time

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
        return files_to_upload or deleted, package_reference, rev_time

    def search(self, pattern=None, ignorecase=True):
        """
        the_files: dict with relative_path: content
        """
        url = self.search_router.search(pattern, ignorecase)
        response = self.get_json(url)["results"]
        return [ConanFileReference.loads(ref) for ref in response]

    def search_packages(self, reference, query):

        if not query:
            url = self.search_router.search_packages(reference)
            package_infos = self.get_json(url)
            return package_infos

        # Read capabilities
        try:
            _, _, capabilities = self.server_info()
        except NotFoundException:
            capabilities = []

        if COMPLEX_SEARCH_CAPABILITY in capabilities:
            url = self.search_router.search_packages(reference, query)
            package_infos = self.get_json(url)
            return package_infos
        else:
            url = self.search_router.search_packages(reference)
            package_infos = self.get_json(url)
            return filter_packages(query, package_infos)

    @handle_return_deserializer()
    def remove_conanfile(self, conan_reference):
        """ Remove a recipe and packages """
        self.check_credentials()
        url = self.conans_router.remove_recipe(conan_reference)
        response = self.requester.delete(url,
                                         auth=self.auth,
                                         headers=self.custom_headers,
                                         verify=self.verify_ssl)
        return response

    def _post_json(self, url, payload):
        response = self.requester.post(url,
                                       auth=self.auth,
                                       headers=self.custom_headers,
                                       verify=self.verify_ssl,
                                       json=payload)
        return response
