
import os
import time

from conans.util.files import sha1sum, exception_message_safe
from conans.util.files.binary_wrapper import open_binary
from conans.errors import ConanException


def upload(requester, output, verify_ssl,  # These were in the constructor
           url, abs_path, auth, dedup, retry, retry_wait, headers):
    """ Functional implementation of the Uploader.upload functionality """

    if dedup:
        dedup_headers = headers.copy() if headers else {}
        dedup_headers.update({"X-Checksum-Deploy": "true", "X-Checksum-Sha1": sha1sum(abs_path)})
        response = requester.put(url, data="", verify=verify_ssl, headers=dedup_headers, auth=auth)
        if response.status_code != 404:
            return response

    headers = headers or {}
    filename = os.path.basename(abs_path)
    pb_desc = "Uploading {}".format(filename)
    file_size = os.stat(abs_path).st_size
    for n_retry in range(retry):
        with open_binary(abs_path, chunk_size=1000, output=output, desc=pb_desc) as f:
            try:
                data = IterableToFileAdapter(f, file_size)
                response = requester.put(url, data=data, verify=verify_ssl, headers=headers,
                                         auth=auth)
                # TODO: Maybe check status code and retry?
                if not response.ok:
                    raise ConanException("Error uploading file: %s, '%s'" % (filename,
                                                                             response.content))

                return response
            except Exception as e:
                msg = exception_message_safe(e)
                output.error(msg)
                if n_retry < (retry - 1):
                    output.info("Waiting %d seconds to retry..." % retry_wait)
                    time.sleep(retry_wait)
                else:
                    raise ConanException("Error uploading file '%s' to %s" % (os.path.basename(
                        abs_path), url))
    return None


class IterableToFileAdapter(object):
    def __init__(self, iterable, file_size):
        self.iterator = iter(iterable)
        self.length = file_size

    def read(self, size=-1):
        return next(self.iterator, b'')

    def __len__(self):
        return self.length

    def __iter__(self):
        return self.iterator.__iter__()


if __name__ == '__main__':
    import requests
    import sys
    from conans.client.output import ConanOutput

    output = ConanOutput(stream=sys.stdout, color=True)

    abs_path = os.path.abspath(__file__)
    r = upload(requests, output=output, verify_ssl=True,
           url='http://httpbin.org/put', abs_path=abs_path, auth=None, dedup=False, retry=2,
           retry_wait=0, headers=None)
    output.writeln(r)

