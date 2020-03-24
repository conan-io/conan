import os
import time

from copy import copy

from conans.client.rest import response_to_str
from conans.errors import AuthenticationException, ConanException, \
    NotFoundException, ForbiddenException, RequestErrorException, InternalErrorException
from conans.util import progress_bar
from conans.util.files import sha1sum


class FileUploader(object):

    def __init__(self, requester, output, verify, config):
        self._output = output
        self._requester = requester
        self._config = config
        self._verify_ssl = verify

    @staticmethod
    def _handle_400_response(response, auth):
        if response.status_code == 400:
            raise RequestErrorException(response_to_str(response))

        if response.status_code == 401:
            raise AuthenticationException(response_to_str(response))

        if response.status_code == 403:
            if auth is None or auth.token is None:
                raise AuthenticationException(response_to_str(response))
            raise ForbiddenException(response_to_str(response))

    def _dedup(self, url, headers, auth):
        """ send the headers to see if it is possible to skip uploading the file, because it
        is already in the server. Artifactory support file deduplication
        """
        dedup_headers = {"X-Checksum-Deploy": "true"}
        if headers:
            dedup_headers.update(headers)
        response = self._requester.put(url, data="", verify=self._verify_ssl, headers=dedup_headers,
                                       auth=auth)
        if response.status_code == 500:
            raise InternalErrorException(response_to_str(response))

        self._handle_400_response(response, auth)

        if response.status_code == 201:  # Artifactory returns 201 if the file is there
            return response

    def upload(self, url, abs_path, auth=None, dedup=False, retry=None, retry_wait=None,
               headers=None, display_name=None):
        retry = retry if retry is not None else self._config.retry
        retry = retry if retry is not None else 1
        retry_wait = retry_wait if retry_wait is not None else self._config.retry_wait
        retry_wait = retry_wait if retry_wait is not None else 5

        # Send always the header with the Sha1
        headers = copy(headers) or {}
        headers["X-Checksum-Sha1"] = sha1sum(abs_path)
        if dedup:
            response = self._dedup(url, headers, auth)
            if response:
                return response

        for counter in range(retry + 1):
            try:
                return self._upload_file(url, abs_path, headers, auth, display_name)
            except (NotFoundException, ForbiddenException, AuthenticationException,
                    RequestErrorException):
                raise
            except ConanException as exc:
                if counter == retry:
                    raise
                else:
                    if self._output:
                        self._output.error(exc)
                        self._output.info("Waiting %d seconds to retry..." % retry_wait)
                    time.sleep(retry_wait)

    def _upload_file(self, url, abs_path,  headers, auth, display_name):
        file_size = os.stat(abs_path).st_size
        file_name = os.path.basename(abs_path)
        description = "Uploading {}".format(file_name)
        post_description = "Uploaded {}".format(
            file_name) if not display_name else "Uploaded {} -> {}".format(file_name, display_name)

        def load_in_chunks(_file):
            """Lazy function (generator) to read a file piece by piece.
            Default chunk size: 1k."""
            while True:
                chunk = _file.read(1024)
                if not chunk:
                    break
                yield chunk

        with open(abs_path, mode='rb') as file_handler:
            progress = progress_bar.Progress(file_size, self._output, description, post_description)
            data = progress.update(load_in_chunks(file_handler))
            iterable_to_file = IterableToFileAdapter(data, file_size)
            try:
                response = self._requester.put(url, data=iterable_to_file, verify=self._verify_ssl,
                                               headers=headers, auth=auth)
                self._handle_400_response(response, auth)
                response.raise_for_status()  # Raise HTTPError for bad http response status
                return response
            except ConanException:
                raise
            except Exception as exc:
                raise ConanException(exc)


class IterableToFileAdapter(object):
    def __init__(self, iterable, total_size):
        self.iterator = iter(iterable)
        self.total_size = total_size

    def read(self, size=-1):  # @UnusedVariable
        return next(self.iterator, b'')

    def __len__(self):
        return self.total_size

    def __iter__(self):
        return self.iterator.__iter__()
