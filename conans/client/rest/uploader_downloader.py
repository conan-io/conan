import os
import time

import conans.tools
from conans.errors import ConanException, NotFoundException
from conans.util.files import sha1sum, exception_message_safe


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


def progress_units(progress, total):
    if total == 0:
        return 0
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
        except NotFoundException:
            raise
        except ConanException as exc:
            if counter == (retry - 1):
                raise
            else:
                msg = exception_message_safe(exc)
                out.error(msg)
                out.info("Waiting %d seconds to retry..." % retry_wait)
                time.sleep(retry_wait)
