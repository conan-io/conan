import os
import time
import traceback

import conans.tools
from conans.errors import ConanException, ConanConnectionError, NotFoundException
from conans.util.files import save, sha1sum, exception_message_safe, to_file_bytes, mkdir
from conans.util.log import logger
from conans.util.tracer import log_download


class Uploader(object):

    def __init__(self, requester, output, verify, chunk_size=1000):
        self.chunk_size = chunk_size
        self.output = output
        self.requester = requester
        self.verify = verify

    def upload(self, url, abs_path, auth=None, dedup=False, retry=1, retry_wait=0, headers=None):
        if dedup:
            dedup_headers = {"X-Checksum-Deploy": "true", "X-Checksum-Sha1": sha1sum(abs_path)}
            if headers:
                dedup_headers.update(headers)
            response = self.requester.put(url, data="", verify=self.verify, headers=dedup_headers,
                                          auth=auth)
            if response.status_code != 404:
                return response

        headers = headers or {}
        self.output.info("")
        # Actual transfer of the real content
        it = load_in_chunks(abs_path, self.chunk_size)
        # Now it is a chunked read file
        file_size = os.stat(abs_path).st_size
        it = upload_with_progress(file_size, it, self.chunk_size, self.output)
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
        except Exception as exc:
            raise ConanException(exception_message_safe(exc))

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
    def __init__(self, totalsize, iterator, chunk_size, output):
        self.totalsize = totalsize
        self.output = output
        self.chunk_size = chunk_size
        self.aprox_chunks = self.totalsize * 1.0 / chunk_size
        self.groups = iterator

    def __iter__(self):
        last_progress = None
        for index, chunk in enumerate(self.groups):
            if self.aprox_chunks == 0:
                index = self.aprox_chunks

            units = progress_units(index, self.aprox_chunks)
            progress = human_readable_progress(index * self.chunk_size, self.totalsize)
            if last_progress != units:  # Avoid screen refresh if nothing has change
                print_progress(self.output, units, progress)
                last_progress = units
            yield chunk

        progress = human_readable_progress(self.totalsize, self.totalsize)
        print_progress(self.output, progress_units(100, 100), progress)

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


class Downloader(object):

    def __init__(self, requester, output, verify, chunk_size=1000):
        self.chunk_size = chunk_size
        self.output = output
        self.requester = requester
        self.verify = verify

    def download(self, url, file_path=None, auth=None, retry=1, retry_wait=0, overwrite=False,
                 headers=None):

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

        t1 = time.time()
        ret = bytearray()
        response = call_with_retry(self.output, retry, retry_wait, self._download_file, url, auth, headers)
        if not response.ok:  # Do not retry if not found or whatever controlled error
            if response.status_code == 404:
                raise NotFoundException("Not found: %s" % url)
            raise ConanException("Error %d downloading file %s" % (response.status_code, url))

        try:
            total_length = response.headers.get('content-length')

            if total_length is None:  # no content length header
                if not file_path:
                    ret += response.content
                else:
                    total_length = len(response.content)
                    progress = human_readable_progress(total_length, total_length)
                    print_progress(self.output, 50, progress)
                    save(file_path, response.content, append=True)
            else:
                total_length = int(total_length)
                encoding = response.headers.get('content-encoding')
                gzip = (encoding == "gzip")
                # chunked can be a problem: https://www.greenbytes.de/tech/webdav/rfc2616.html#rfc.section.4.4
                # It will not send content-length or should be ignored

                def download_chunks(file_handler=None, ret_buffer=None):
                    """Write to a buffer or to a file handler"""
                    chunk_size = 1024 if not file_path else 1024 * 100
                    download_size = 0
                    last_progress = None
                    for data in response.iter_content(chunk_size=chunk_size):
                        download_size += len(data)
                        if ret_buffer is not None:
                            ret_buffer.extend(data)
                        if file_handler is not None:
                            file_handler.write(to_file_bytes(data))

                        units = progress_units(download_size, total_length)
                        progress = human_readable_progress(download_size, total_length)
                        if last_progress != units:  # Avoid screen refresh if nothing has change
                            if self.output:
                                print_progress(self.output, units, progress)
                            last_progress = units
                    return download_size

                if file_path:
                    mkdir(os.path.dirname(file_path))
                    with open(file_path, 'wb') as handle:
                        dl_size = download_chunks(file_handler=handle)
                else:
                    dl_size = download_chunks(ret_buffer=ret)

                if dl_size != total_length and not gzip:
                    raise ConanException("Transfer interrupted before "
                                         "complete: %s < %s" % (dl_size, total_length))

            duration = time.time() - t1
            log_download(url, duration)

            if not file_path:
                return bytes(ret)
            else:
                return
        except Exception as e:
            logger.debug(e.__class__)
            logger.debug(traceback.format_exc())
            # If this part failed, it means problems with the connection to server
            raise ConanConnectionError("Download failed, check server, possibly try again\n%s"
                                       % str(e))

    def _download_file(self, url, auth, headers):
        try:
            response = self.requester.get(url, stream=True, verify=self.verify, auth=auth,
                                          headers=headers)
        except Exception as exc:
            raise ConanException("Error downloading file %s: '%s'" % (url, exception_message_safe(exc)))

        return response


def progress_units(progress, total):
    return min(50, int(50 * progress / total))


def human_readable_progress(bytes_transferred, total_bytes):
    return "%s/%s" % (conans.tools.human_size(bytes_transferred),
                      conans.tools.human_size(total_bytes))


def print_progress(output, units, progress=""):
    if output.is_terminal:
        output.rewrite_line("[%s%s] %s" % ('=' * units, ' ' * (50 - units), progress))


def call_with_retry(out, retry, retry_wait, method, *args, **kwargs):
    for counter in range(retry):
        try:
            return method(*args, **kwargs)
        except ConanException as exc:
            if counter == (retry - 1):
                raise
            else:
                msg = exception_message_safe(exc)
                out.error(msg)
                out.info("Waiting %d seconds to retry..." % retry_wait)
                time.sleep(retry_wait)
