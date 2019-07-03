import os
import traceback
import time

from tqdm import tqdm

from conans.client.rest import response_to_str
from conans.errors import AuthenticationException, ConanConnectionError, ConanException, \
    NotFoundException, ForbiddenException, RequestErrorException
from conans.util.files import mkdir, save_append, sha1sum, to_file_bytes
from conans.util.log import logger
from conans.util.tracer import log_download

TIMEOUT_BEAT_SECONDS = 30
TIMEOUT_BEAT_CHARACTER = '.'


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
        headers = headers or {}
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
                if auth.token is None:
                    raise AuthenticationException(response_to_str(response))
                raise ForbiddenException(response_to_str(response))
            if response.status_code == 201:  # Artifactory returns 201 if the file is there
                return response

        if not self.output.is_terminal:
            self.output.info("")
        # Actual transfer of the real content
        it = load_in_chunks(abs_path, self.chunk_size)
        # Now it is a chunked read file
        file_size = os.stat(abs_path).st_size
        file_name = os.path.basename(abs_path)
        it = upload_with_progress(file_size, it, self.chunk_size, self.output, file_name)
        # Now it will print progress in each iteration
        iterable_to_file = IterableToFileAdapter(it, file_size)
        # Now it is prepared to work with request
        ret = call_with_retry(self.output, retry, retry_wait, self._upload_file, url,
                              data=iterable_to_file, headers=headers, auth=auth)

        return ret

    def _upload_file(self, url, data,  headers, auth):
        try:
            response = self.requester.put(url, data=data, verify=self.verify,
                                          headers=headers, auth=auth)

            if response.status_code == 400:
                raise RequestErrorException(response_to_str(response))

            if response.status_code == 401:
                raise AuthenticationException(response_to_str(response))

            if response.status_code == 403:
                if auth.token is None:
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


class upload_with_progress(object):
    def __init__(self, totalsize, iterator, chunk_size, output, file_name):
        self.totalsize = totalsize
        self.output = output
        self.chunk_size = chunk_size
        self.aprox_chunks = self.totalsize * 1.0 / chunk_size
        self.groups = iterator
        self.file_name = file_name
        self.last_time = 0

    def __iter__(self):
        progress_bar = None
        if self.output and self.output.is_terminal:
            progress_bar = tqdm(total=self.totalsize, unit='B', unit_scale=True,
                                unit_divisor=1024, desc="Uploading {}".format(self.file_name),
                                leave=True, dynamic_ncols=False, ascii=True, file=self.output)
        for index, chunk in enumerate(self.groups):
            if progress_bar is not None:
                update_size = self.chunk_size if (index + 1) * self.chunk_size < self.totalsize \
                    else self.totalsize - self.chunk_size * index
                progress_bar.update(update_size)
            elif self.output and time.time() - self.last_time > TIMEOUT_BEAT_SECONDS:
                self.last_time = time.time()
                self.output.write(TIMEOUT_BEAT_CHARACTER)
            yield chunk

        if progress_bar is not None:
            progress_bar.close()
        elif self.output:
            self.output.writeln(TIMEOUT_BEAT_CHARACTER)

    def __len__(self):
        return self.totalsize


def load_in_chunks(path, chunk_size=1024):
    """Lazy function (generator) to read a file piece by piece.
    Default chunk size: 1k."""
    with open(path, 'rb') as file_object:
        while True:
            data = file_object.read(chunk_size)
            if not data:
                break
            yield data


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
                if auth.token is None:
                    raise AuthenticationException(response_to_str(response))
                raise ForbiddenException(response_to_str(response))
            elif response.status_code == 401:
                raise AuthenticationException()
            raise ConanException("Error %d downloading file %s" % (response.status_code, url))

        try:
            logger.debug("DOWNLOAD: %s" % url)
            data = self._download_data(response, file_path)
            duration = time.time() - t1
            log_download(url, duration)
            return data
        except Exception as e:
            logger.debug(e.__class__)
            logger.debug(traceback.format_exc())
            # If this part failed, it means problems with the connection to server
            raise ConanConnectionError("Download failed, check server, possibly try again\n%s"
                                       % str(e))

    def _download_data(self, response, file_path):
        ret = bytearray()
        total_length = response.headers.get('content-length')

        progress_bar = None
        if self.output and self.output.is_terminal:
            progress_bar = tqdm(unit='B', unit_scale=True,
                                unit_divisor=1024, dynamic_ncols=False,
                                leave=True, ascii=True, file=self.output)

        if total_length is None:  # no content length header
            if not file_path:
                ret += response.content
            else:
                if self.output:
                    total_length = len(response.content)
                    if progress_bar is not None:
                        progress_bar.desc = "Downloading {}".format(os.path.basename(file_path))
                        progress_bar.total = total_length
                        progress_bar.update(total_length)

                save_append(file_path, response.content)
        else:
            total_length = int(total_length)
            encoding = response.headers.get('content-encoding')
            gzip = (encoding == "gzip")
            # chunked can be a problem:
            # https://www.greenbytes.de/tech/webdav/rfc2616.html#rfc.section.4.4
            # It will not send content-length or should be ignored
            if progress_bar is not None:
                progress_bar.total = total_length

            def download_chunks(file_handler=None, ret_buffer=None):
                """Write to a buffer or to a file handler"""
                chunk_size = 1024 if not file_path else 1024 * 100
                download_size = 0
                last_time = 0
                if progress_bar is not None:
                    progress_bar.desc = "Downloading {}".format(os.path.basename(file_path))

                for data in response.iter_content(chunk_size):
                    download_size += len(data)
                    if ret_buffer is not None:
                        ret_buffer.extend(data)
                    if file_handler is not None:
                        file_handler.write(to_file_bytes(data))
                    if progress_bar is not None:
                        progress_bar.update(len(data))
                    elif self.output and time.time() - last_time > TIMEOUT_BEAT_SECONDS:
                        last_time = time.time()
                        self.output.write(TIMEOUT_BEAT_CHARACTER)

                return download_size

            if file_path:
                mkdir(os.path.dirname(file_path))
                with open(file_path, 'wb') as handle:
                    dl_size = download_chunks(file_handler=handle)
            else:
                dl_size = download_chunks(ret_buffer=ret)

            response.close()

            if dl_size != total_length and not gzip:
                raise ConanException("Transfer interrupted before "
                                     "complete: %s < %s" % (dl_size, total_length))

        if progress_bar is not None:
            progress_bar.close()
        elif self.output:
            self.output.writeln(TIMEOUT_BEAT_CHARACTER)

        if not file_path:
            return bytes(ret)
        else:
            return


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
