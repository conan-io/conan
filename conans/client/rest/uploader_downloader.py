from conans.errors import ConanException


class Uploader(object):

    def __init__(self, requester, output, verify, chunk_size=1000):
        self.chunk_size = chunk_size
        self.output = output
        self.requester = requester
        self.verify = verify

    def post(self, url, content):
        self.output.info("")
        return self.requester.put(url, data=content, verify=self.verify)


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

def progress_units(progress, total):
    return int(50 * progress / total)


def print_progress(output, units):
    output.rewrite_line("[%s%s]" % ('=' * units, ' ' * (50 - units)))
