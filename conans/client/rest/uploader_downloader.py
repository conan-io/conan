import os
import traceback
import time
from copy import copy

import six

from conans.util import progress_bar
from conans.client.rest import response_to_str
from conans.errors import AuthenticationException, ConanConnectionError, ConanException, \
    NotFoundException, ForbiddenException, RequestErrorException
from conans.util.files import mkdir, sha1sum
from conans.util.log import logger
from conans.util.tracer import log_download


class FileUploader(object):

    def __init__(self, requester, output, verify, chunk_size=1000):
        self.chunk_size = chunk_size
        self.output = output
        self.requester = requester
        self.verify = verify

    def upload(self, url, abs_path, auth=None, dedup=False, retry=None, retry_wait=None,
               headers=None):
        retry = retry if retry is not None else self.requester.retry
        retry = retry if retry is not None else 1
        retry_wait = retry_wait if retry_wait is not None else self.requester.retry_wait
        retry_wait = retry_wait if retry_wait is not None else 5

        # Send always the header with the Sha1
        headers = copy(headers) or {}
        headers["X-Checksum-Sha1"] = sha1sum(abs_path)
        if dedup:
            dedup_headers = {"X-Checksum-Deploy": "true"}
            if headers:
                dedup_headers.update(headers)
            response = self.requester.put(url, data="", verify=self.verify, headers=dedup_headers,
                                          auth=auth)
            if response.status_code == 400:
                raise RequestErrorException(response_to_str(response))

            if response.status_code == 401:
                raise AuthenticationException(response_to_str(response))

            if response.status_code == 403:
                if auth is None or auth.token is None:
                    raise AuthenticationException(response_to_str(response))
                raise ForbiddenException(response_to_str(response))
            if response.status_code == 201:  # Artifactory returns 201 if the file is there
                return response

        ret = call_with_retry(self.output, retry, retry_wait, self._upload_file, url,
                              abs_path=abs_path, headers=headers, auth=auth)
        return ret

    def _upload_file(self, url, abs_path,  headers, auth):

        file_size = os.stat(abs_path).st_size
        file_name = os.path.basename(abs_path)
        description = "Uploading {}".format(file_name)

        def load_in_chunks(_file, size):
            """Lazy function (generator) to read a file piece by piece.
            Default chunk size: 1k."""
            while True:
                chunk = _file.read(size)
                if not chunk:
                    break
                yield chunk

        with open(abs_path, mode='rb') as file_handler:
            progress = progress_bar.Progress(file_size, self.output, description, print_dot=True)
            chunk_size = 1024
            data = progress.update(load_in_chunks(file_handler, chunk_size), chunk_size)
            iterable_to_file = IterableToFileAdapter(data, file_size)
            try:
                response = self.requester.put(url, data=iterable_to_file, verify=self.verify,
                                              headers=headers, auth=auth)

                if response.status_code == 400:
                    raise RequestErrorException(response_to_str(response))

                if response.status_code == 401:
                    raise AuthenticationException(response_to_str(response))

                if response.status_code == 403:
                    if auth is None or auth.token is None:
                        raise AuthenticationException(response_to_str(response))
                    raise ForbiddenException(response_to_str(response))

                response.raise_for_status()  # Raise HTTPError for bad http response status

            except ConanException:
                raise
            except Exception as exc:
                raise ConanException(exc)

        return response


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


class FileDownloader(object):

    def __init__(self, requester, output, verify, chunk_size=1000):
        self.chunk_size = chunk_size
        self.output = output
        self.requester = requester
        self.verify = verify

    def download(self, url, file_path=None, auth=None, retry=None, retry_wait=None, overwrite=False,
                 headers=None):
        retry = retry if retry is not None else self.requester.retry
        retry = retry if retry is not None else 2
        retry_wait = retry_wait if retry_wait is not None else self.requester.retry_wait
        retry_wait = retry_wait if retry_wait is not None else 0

        if file_path and not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)

        if file_path and os.path.exists(file_path):
            if overwrite:
                if self.output:
                    self.output.warn("file '%s' already exists, overwriting" % file_path)
            else:
                # Should not happen, better to raise, probably we had to remove
                # the dest folder before
                raise ConanException("Error, the file to download already exists: '%s'" % file_path)

        return call_with_retry(self.output, retry, retry_wait, self._download_file, url, auth,
                               headers, file_path)

    def _download_file(self, url, auth, headers, file_path):
        t1 = time.time()
        try:
            response = self.requester.get(url, stream=True, verify=self.verify, auth=auth,
                                          headers=headers)
        except Exception as exc:
            raise ConanException("Error downloading file %s: '%s'" % (url, exc))

        if not response.ok:
            if response.status_code == 404:
                raise NotFoundException("Not found: %s" % url)
            elif response.status_code == 403:
                if auth is None or (hasattr(auth, "token") and auth.token is None):
                    # TODO: This is a bit weird, why this conversion? Need to investigate
                    raise AuthenticationException(response_to_str(response))
                raise ForbiddenException(response_to_str(response))
            elif response.status_code == 401:
                raise AuthenticationException()
            raise ConanException("Error %d downloading file %s" % (response.status_code, url))

        def read_response(size):
            for chunk in response.iter_content(size):
                yield chunk

        def write_chunks(chunks, path):
            ret = None
            downloaded_size = 0
            if path:
                mkdir(os.path.dirname(path))
                with open(path, 'wb') as file_handler:
                    for chunk in chunks:
                        assert ((six.PY3 and isinstance(chunk, bytes)) or
                                (six.PY2 and isinstance(chunk, str)))
                        file_handler.write(chunk)
                        downloaded_size += len(chunk)
            else:
                ret_data = bytearray()
                for chunk in chunks:
                    ret_data.extend(chunk)
                    downloaded_size += len(chunk)
                ret = bytes(ret_data)
            return ret, downloaded_size

        try:
            logger.debug("DOWNLOAD: %s" % url)
            total_length = response.headers.get('content-length') or len(response.content)
            total_length = int(total_length)
            description = "Downloading {}".format(os.path.basename(file_path)) if file_path else None
            progress = progress_bar.Progress(total_length, self.output, description, print_dot=False)

            chunk_size = 1024 if not file_path else 1024 * 100
            encoding = response.headers.get('content-encoding')
            gzip = (encoding == "gzip")

            written_chunks, total_downloaded_size = write_chunks(
                progress.update(read_response(chunk_size), chunk_size),
                file_path
            )

            response.close()
            if total_downloaded_size != total_length and not gzip:
                raise ConanException("Transfer interrupted before "
                                     "complete: %s < %s" % (total_downloaded_size, total_length))

            duration = time.time() - t1
            log_download(url, duration)
            return written_chunks

        except Exception as e:
            logger.debug(e.__class__)
            logger.debug(traceback.format_exc())
            # If this part failed, it means problems with the connection to server
            raise ConanConnectionError("Download failed, check server, possibly try again\n%s"
                                       % str(e))


def print_progress(output, units, progress=""):
    if output.is_terminal:
        output.rewrite_line("[%s%s] %s" % ('=' * units, ' ' * (50 - units), progress))


def call_with_retry(out, retry, retry_wait, method, *args, **kwargs):
    for counter in range(retry + 1):
        try:
            return method(*args, **kwargs)
        except (NotFoundException, ForbiddenException, AuthenticationException,
                RequestErrorException):
            raise
        except ConanException as exc:
            if counter == retry:
                raise
            else:
                if out:
                    out.error(exc)
                    out.info("Waiting %d seconds to retry..." % retry_wait)
                time.sleep(retry_wait)
