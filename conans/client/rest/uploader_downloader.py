from conans.errors import ConanException, ConanConnectionError
from conans.util.log import logger
import traceback
from conans.util.files import save
from conans.util.sha import sha1


class Uploader(object):

    def __init__(self, requester, output, verify, chunk_size=1000):
        self.chunk_size = chunk_size
        self.output = output
        self.requester = requester
        self.verify = verify

    def upload(self, url, content, auth=None):
        self.output.info("")
        headers = {"X-Checksum-Deploy": "true",
                   "X-Checksum-Sha1": sha1(content)}
        response = self.requester.put(url, data="", verify=self.verify, headers=headers, auth=auth)
        if response.status_code == 404:
            it = upload_in_chunks(content, self.chunk_size, self.output)
            return self.requester.put(url, data=IterableToFileAdapter(it), verify=self.verify,
                                      headers=None, auth=auth)
        return response


class Downloader(object):

    def __init__(self, requester, output, verify, chunk_size=1000):
        self.chunk_size = chunk_size
        self.output = output
        self.requester = requester
        self.verify = verify

    def download(self, url, file_path=None, auth=None):
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

            return bytes(ret)
        except Exception as e:
            logger.debug(e.__class__)
            logger.debug(traceback.format_exc())
            # If this part failed, it means problems with the connection to server
            raise ConanConnectionError("Download failed, check server, possibly try again\n%s"
                                       % str(e))


class upload_in_chunks(object):
    def __init__(self, content, chunksize, output):
        self.totalsize = len(content)
        self.output = output
        self.aprox_chunks = self.totalsize * 1.0 / chunksize
        self.groups = chunker(content, chunksize)

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


def chunker(seq, size):
    return (seq[pos:pos + size] for pos in range(0, len(seq), size))


def progress_units(progress, total):
    return int(50 * progress / total)


def print_progress(output, units):
    output.rewrite_line("[%s%s]" % ('=' * units, ' ' * (50 - units)))


class IterableToFileAdapter(object):
    def __init__(self, iterable):
        self.iterator = iter(iterable)
        self.length = len(iterable)

    def read(self, size=-1):  # @UnusedVariable
        return next(self.iterator, b'')

    def __len__(self):
        return self.length

    def __iter__(self):
        return self.iterator.__iter__()
