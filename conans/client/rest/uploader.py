
import os
import time

from conans.util.files import sha1sum, exception_message_safe
from conans.util.files.binary_wrapper import open_binary


def upload(requester, output, verify_ssl,  # These were in the constructor
           url, abs_path, auth, dedup, retry, retry_wait, headers):
    """ Functional implementation of the Uploader.upload functionality """

    if dedup:
        dedup_headers = headers.copy() if headers else {}
        dedup_headers.update({"X-Checksum-Deploy": "true", "X-Checksum-Sha1": sha1sum(abs_path)})
        response = requester.put(url, data="", verify=verify_ssl, headers=dedup_headers, auth=auth)
        if response.status_code != 404:
            return response  # TODO: return a ConanFuture

    headers = headers or {}
    with open_binary(abs_path, chunk_size=250, output=output) as f:
        file_size = os.stat(abs_path).st_size
        for _ in range(retry):
            try:
                data = IterableToFileAdapter(f, file_size)
                response = requester.put(url, data=data, verify=verify_ssl, headers=headers,
                                         auth=auth)
                # TODO: Maybe check status code and retry?
                return response
            except Exception as e:
                msg = exception_message_safe(e)
                output.error(msg)
                output.info("Waiting %d seconds to retry..." % retry_wait)
                time.sleep(retry_wait)
    return None


class IterableToFileAdapter(object):
    def __init__(self, iterable, file_size):
        self.iterator = iter(iterable)
        self.length = file_size

    def read(self, size=-1):
        return next(self.iterator, b'')

    def __len__(self):
        return self.length


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

