from conans.errors import ConanException, ConanConnectionError
from conans.util.log import logger
import traceback
from conans.util.files import save, sha1sum
import os


class Uploader(object):

    def __init__(self, requester, output, verify, chunk_size=1000):
        self.chunk_size = chunk_size
        self.output = output
        self.requester = requester
        self.verify = verify

    def upload(self, url, abs_path, auth=None, dedup=False):
        if dedup:
            headers = {"X-Checksum-Deploy": "true",
                       "X-Checksum-Sha1": sha1sum(abs_path)}
            response = self.requester.put(url, data="", verify=self.verify, headers=headers,
                                          auth=auth)
            if response.status_code != 404:
                return response

        self.output.info("")
        # Actual transfer of the real content
        it = load_in_chunks(abs_path, self.chunk_size)
        # Now it is a chunked read file
        file_size = os.stat(abs_path).st_size
        it = upload_with_progress(file_size, it, self.chunk_size, self.output)
        # Now it will print progress in each iteration
        iterable_to_file = IterableToFileAdapter(it, file_size)
        # Now it is prepared to work with request
        ret = self.requester.put(url, data=iterable_to_file, verify=self.verify, headers=None, auth=auth)
        return ret


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
        self.aprox_chunks = self.totalsize * 1.0 / chunk_size
        self.groups = iterator

    def __iter__(self):
        last_progress = None
        for index, chunk in enumerate(self.groups):
            if self.aprox_chunks == 0:
                index = self.aprox_chunks

            units = progress_units(index, self.aprox_chunks)
            if last_progress != units:  # Avoid screen refresh if nothing has change
                print_progress(self.output, units)
                last_progress = units
            yield chunk

        print_progress(self.output, progress_units(100, 100))

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

    def download(self, url, file_path=None, auth=None):

        if file_path and os.path.exists(file_path):
            # Should not happen, better to raise, probably we had to remove the dest folder before
            raise ConanException("Error, the file to download already exists: '%s'" % file_path)

        ret = bytearray()
        response = self.requester.get(url, stream=True, verify=self.verify, auth=auth)
        if not response.ok:
            raise ConanException("Error %d downloading file %s" % (response.status_code, url))

        try:
            total_length = response.headers.get('content-length')

            if total_length is None:  # no content length header
                if not file_path:
                    ret += response.content
                else:
                    save(file_path, response.content, append=True)
            else:
                dl = 0
                total_length = int(total_length)
                last_progress = None
                chunk_size = 1024 if not file_path else 1024 * 100
                for data in response.iter_content(chunk_size=chunk_size):
                    dl += len(data)
                    if not file_path:
                        ret.extend(data)
                    else:
                        save(file_path, data, append=True)

                    units = progress_units(dl, total_length)
                    if last_progress != units:  # Avoid screen refresh if nothing has change
                        if self.output:
                            print_progress(self.output, units)
                        last_progress = units
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


def progress_units(progress, total):
    return int(50 * progress / total)


def print_progress(output, units):
    if output.is_terminal():
        output.rewrite_line("[%s%s]" % ('=' * units, ' ' * (50 - units)))
