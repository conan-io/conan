from conans.errors import ConanException, ConanConnectionError


class Uploader(object):

    def __init__(self, requester, output, verify, chunk_size=1000):
        self.chunk_size = chunk_size
        self.output = output
        self.requester = requester
        self.verify = verify

    def post(self, url, content):
        self.output.info("")
        it = upload_in_chunks(content, self.chunk_size, self.output)
        return self.requester.put(url, data=IterableToFileAdapter(it), verify=self.verify)


class Downloader(object):

    def __init__(self, requester, output, verify, chunk_size=1000):
        self.chunk_size = chunk_size
        self.output = output
        self.requester = requester
        self.verify = verify

    def download(self, url):
        ret = b""
        response = self.requester.get(url, stream=True, verify=self.verify)
        if not response.ok:
            raise ConanException("Error %d downloading file %s" % (response.status_code, url))

        try:
            total_length = response.headers.get('content-length')

            if total_length is None:  # no content length header
                ret += response.content
            else:
                dl = 0
                total_length = int(total_length)
                last_progress = None
                for data in response.iter_content(chunk_size=1024):
                    dl += len(data)
                    ret += data
                    units = progress_units(dl, total_length)
                    if last_progress != units:  # Avoid screen refresh if nothing has change
                        if self.output:
                            print_progress(self.output, units)
                        last_progress = units

            return ret
        except Exception as e:
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
