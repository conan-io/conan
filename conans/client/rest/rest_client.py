from conans.errors import EXCEPTION_CODE_MAPPING, NotFoundException,\
    ConanException
from requests.auth import AuthBase, HTTPBasicAuth
from conans.util.log import logger
from conans.info import SearchInfo
import json
from conans.paths import CONANFILE, CONAN_MANIFEST
import time
from conans.client.rest.differ import diff_snapshots
from conans.util.files import md5
import os
from conans.model.manifest import FileTreeManifest
from conans.client.rest.uploader_downloader import Uploader, Downloader


def handle_return_deserializer(deserializer=None):
    """Decorator for rest api methods.
    Map exceptions and http return codes and deserialize if needed.

    deserializer: Function for deserialize values"""
    def handle_return(method):
        def inner(*argc, **argv):
            ret = method(*argc, **argv)
            if ret.status_code != 200:
                raise get_exception_from_error(ret.status_code)(ret.content)
            return deserializer(ret.content) if deserializer else ret.content
        return inner
    return handle_return


def get_exception_from_error(error_code):
    try:
        tmp = {value: key for key, value in EXCEPTION_CODE_MAPPING.iteritems()}
        if error_code in tmp:
            logger.debug("From server: %s" % str(tmp[error_code]))
            return tmp[error_code]
        else:
            logger.debug("From server: %s" % str(_base_error(error_code)))
            return tmp[_base_error(error_code)]
    except KeyError:
        return None


def _base_error(error_code):
    return int(str(error_code)[0] + "00")


class JWTAuth(AuthBase):
    """Attaches JWT Authentication to the given Request object."""
    def __init__(self, token):
        self.token = token

    def __call__(self, request):
        if self.token:
            request.headers['Authorization'] = "Bearer %s" % self.token
        return request


class RestApiClient(object):
    """
        Rest Api Client for handle remote.
    """
    import cacert
    # Necessary for pyinstaller, because it doesn't copy the cacert.
    # It should not be necessary anymore the own conan.io certificate (fixed in server)
    VERIFY_SSL = cacert.file_path

    def __init__(self, output, requester):
        # Set to instance
        self.token = None
        self.remote_url = None
        self.custom_headers = {}  # Can set custom headers to each request
        self._output = output
        self.requester = requester

    @property
    def auth(self):
        return JWTAuth(self.token)

    def get_conan_digest(self, conan_reference):
        """Gets a FileTreeManifest from conans"""

        # Obtain the URLs
        url = "%s/conans/%s/digest" % (self._remote_api_url, "/".join(conan_reference))
        urls = self._get_json(url)

        # Get the digest
        contents = self.download_files(urls)
        contents = dict(contents)  # Unroll generator
        return FileTreeManifest.loads(contents[CONAN_MANIFEST])

    def get_package_digest(self, package_reference):
        """Gets a FileTreeManifest from conans"""

        # Obtain the URLs
        url = "%s/conans/%s/packages/%s/digest" % (self._remote_api_url,
                                                   "/".join(package_reference.conan),
                                                   package_reference.package_id)
        urls = self._get_json(url)

        # Get the digest
        contents = self.download_files(urls)
        contents = dict(contents)  # Unroll generator
        return FileTreeManifest.loads(contents[CONAN_MANIFEST])

    def get_conanfile(self, conan_reference):
        """Gets a dict of filename:contents from conans"""
        # Get the conanfile snapshot first
        url = "%s/conans/%s/download_urls" % (self._remote_api_url, "/".join(conan_reference))
        urls = self._get_json(url)

        if CONANFILE not in urls.keys():
            raise NotFoundException("Conan '%s' doesn't have a %s!" % (conan_reference, CONANFILE))

        # TODO: Get fist an snapshot and compare files and download only required?

        # Download the resources
        contents = self.download_files(urls, self._output)
        return contents

    def get_package(self, package_reference):
        """Gets a dict of filename:contents from package"""
        url = "%s/conans/%s/packages/%s/download_urls" % (self._remote_api_url,
                                                          "/".join(package_reference.conan),
                                                          package_reference.package_id)
        urls = self._get_json(url)
        if not urls:
            raise NotFoundException("Package not found!")
        # TODO: Get fist an snapshot and compare files and download only required?

        # Download the resources
        contents = self.download_files(urls, self._output)
        return contents

    def upload_conan(self, conan_reference, the_files):
        """
        the_files: dict with relative_path: content
        """
        self.check_credentials()

        # Get the remote snapshot
        remote_snapshot = self._get_conan_snapshot(conan_reference)
        local_snapshot = {filename: md5(content) for filename, content in the_files.iteritems()}

        # Get the diff
        new, modified, deleted = diff_snapshots(local_snapshot, remote_snapshot)

        files_to_upload = {filename.replace("\\", "/"): the_files[filename] for filename in new + modified}
        if files_to_upload:
            # Get the upload urls
            url = "%s/conans/%s/upload_urls" % (self._remote_api_url, "/".join(conan_reference))
            filesizes = {filename.replace("\\", "/"): len(content) for filename, content in files_to_upload.iteritems()}
            urls = self._get_json(url, data=filesizes)
            self.upload_files(urls, files_to_upload, self._output)
        if deleted:
            self.remove_conanfile_files(conan_reference, deleted)

    def upload_package(self, package_reference, the_files):
        """
        basedir: Base directory with the files to upload (for read the files in disk)
        relative_files: relative paths to upload
        """
        self.check_credentials()

        # Get the remote snapshot
        remote_snapshot = self._get_package_snapshot(package_reference)
        local_snapshot = {filename: md5(content) for filename, content in the_files.iteritems()}

        # Get the diff
        new, modified, deleted = diff_snapshots(local_snapshot, remote_snapshot)

        files_to_upload = {filename: the_files[filename] for filename in new + modified}
        if files_to_upload:        # Obtain upload urls
            url = "%s/conans/%s/packages/%s/upload_urls" % (self._remote_api_url,
                                                            "/".join(package_reference.conan),
                                                            package_reference.package_id)
            filesizes = {filename: len(content) for filename, content in files_to_upload.iteritems()}
            self._output.rewrite_line("Requesting upload permissions...")
            urls = self._get_json(url, data=filesizes)
            self._output.rewrite_line("Requesting upload permissions...Done!")
            self._output.writeln("")
            self.upload_files(urls, files_to_upload, self._output)
        else:
            self._output.rewrite_line("Package is up to date.")
            self._output.writeln("")
        if deleted:
            self.remove_package_files(package_reference, deleted)

    @handle_return_deserializer()
    def authenticate(self, user, password):
        '''Sends user + password to get a token'''
        auth = HTTPBasicAuth(user, password)
        path = "%s/users/authenticate" % self._remote_api_url
        ret = self.requester.get(path, auth=auth, headers=self.custom_headers,
                                 verify=self.VERIFY_SSL)
        return ret

    @handle_return_deserializer()
    def check_credentials(self):
        """If token is not valid will raise ForbiddenException or AuthenticationException.
        User will be asked for new user/pass"""
        url = "%s/users/check_credentials" % self._remote_api_url
        ret = self.requester.get(url, auth=self.auth, headers=self.custom_headers,
                                 verify=self.VERIFY_SSL)
        return ret

    @handle_return_deserializer(SearchInfo.deserialize)
    def search(self, pattern=None, ignorecase=True):
        """
        the_files: dict with relative_path: content
        """
        query = ''
        if pattern:
            case_sensitive = "&ignorecase=False" if not ignorecase else ''
            pattern = "q=%s" % pattern
            query = "?%s%s" % (pattern, case_sensitive)

        url = "%s/conans/search%s" % (self._remote_api_url, query)
        response = self.requester.get(url,
                                      auth=self.auth,
                                      headers=self.custom_headers,
                                      verify=self.VERIFY_SSL)
        return response

    @handle_return_deserializer()
    def remove_conanfile(self, conan_reference):
        """ Remove any conans
        """
        self.check_credentials()
        url = "%s/conans/%s" % (self._remote_api_url, '/'.join(conan_reference))
        response = self.requester.delete(url,
                                         auth=self.auth,
                                         headers=self.custom_headers,
                                         verify=self.VERIFY_SSL)
        return response

    def remove_packages(self, conan_reference, package_ids=None):
        """ Remove any conans
        """
        self.check_credentials()
        payload = {"package_ids": package_ids}
        url = "%s/conans/%s/packages/delete" % (self._remote_api_url, '/'.join(conan_reference))
        response = self.requester.post(url,
                                       auth=self.auth,
                                       headers=self.custom_headers,
                                       verify=self.VERIFY_SSL,
                                       json=payload)
        return response

    @handle_return_deserializer()
    def remove_conanfile_files(self, conan_reference, files):
        """ Remove any conans
        """
        self.check_credentials()
        payload = {"files": [filename.replace("\\", "/") for filename in files]}
        url = "%s/conans/%s/remove_files" % (self._remote_api_url, '/'.join(conan_reference))
        response = self.requester.post(url,
                                       auth=self.auth,
                                       headers=self.custom_headers,
                                       verify=self.VERIFY_SSL,
                                       json=payload)
        return response

    @handle_return_deserializer()
    def remove_package_files(self, package_reference, files):
        """ Remove any conans
        """
        self.check_credentials()
        payload = {"files": [filename.replace("\\", "/") for filename in files]}
        url = "%s/conans/%s/packages/%s/remove_files" % (self._remote_api_url,
                                                         "/".join(package_reference.conan),
                                                         package_reference.package_id)
        response = self.requester.post(url,
                                       auth=self.auth,
                                       headers=self.custom_headers,
                                       verify=self.VERIFY_SSL,
                                       json=payload)
        return response

    def _get_conan_snapshot(self, reference):
        url = "%s/conans/%s" % (self._remote_api_url, '/'.join(reference))
        try:
            snapshot = self._get_json(url)
        except NotFoundException:
            snapshot = {}
        norm_snapshot = {os.path.normpath(filename): the_md5
                         for filename, the_md5 in snapshot.iteritems()}
        return norm_snapshot

    def _get_package_snapshot(self, package_reference):
        url = "%s/conans/%s/packages/%s" % (self._remote_api_url,
                                            "/".join(package_reference.conan),
                                            package_reference.package_id)
        try:
            snapshot = self._get_json(url)
        except NotFoundException:
            snapshot = {}
        norm_snapshot = {os.path.normpath(filename): the_md5
                         for filename, the_md5 in snapshot.iteritems()}
        return norm_snapshot

    def _get_json(self, url, data=None):
        if data:  # POST request
            headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
            headers.update(self.custom_headers)
            response = self.requester.post(url, auth=self.auth, headers=headers,
                                           verify=self.VERIFY_SSL,
                                           stream=True,
                                           data=json.dumps(data))
        else:
            response = self.requester.get(url, auth=self.auth, headers=self.custom_headers,
                                          verify=self.VERIFY_SSL,
                                          stream=True)
        if response.status_code != 200:
            raise get_exception_from_error(response.status_code)(response.content)

        return json.loads(response.content)

    @property
    def _remote_api_url(self):
        return "%s/v1" % self.remote_url

    def download_files(self, file_urls, output=None):
        """
        :param: file_urls is a dict with {filename: url}

        Its a generator, so it yields elements for memory performance
        """
        downloader = Downloader(self.requester, output, self.VERIFY_SSL)
        for filename, resource_url in file_urls.iteritems():
            if output:
                output.writeln("Downloading %s" % filename)
            contents = downloader.download(resource_url)
            if output:
                output.writeln("")
            yield os.path.normpath(filename), contents

    def upload_files(self, file_urls, files, output):
        t1 = time.time()
        failed = {}
        uploader = Uploader(self.requester, output, self.VERIFY_SSL)
        for filename, resource_url in file_urls.iteritems():
            output.rewrite_line("Uploading %s" % filename)
            response = uploader.post(resource_url, files[filename])
            output.writeln("")
            if not response.ok:
                output.error("\nError uploading file: %s" % filename)
                logger.debug(response.content)
                failed[filename] = resource_url
            else:
                pass

        if failed:
            logger.debug(failed)
            output.warn("\nThe upload of some files has failed. "
                        "Execute upload again to retry upload the failed files.")
            raise ConanException("Upload failed!")
        else:
            logger.debug("\nAll uploaded! Total time: %s\n" % str(time.time() - t1))

  