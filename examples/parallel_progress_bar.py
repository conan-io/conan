
import os
import concurrent.futures
import requests

from conans.client.rest.downloader import download
from conans.util.log import logger
from conans.client.output import ConanOutput


# Retrieve a single page and report the url and contents
def download_worker(url, outputrr):
    output = ConanOutput(stream=sys.stdout, color=True)
    r = download(requests, output=output, verify_ssl=True,
                 url=url, file_path=None, auth=None, retry=2,
                 retry_wait=0, overwrite=True, headers=None)
    output.info("Done!")
    return "er"


if __name__ == '__main__':
    import sys
    import requests

    output = ConanOutput(stream=sys.stdout, color=True)

    urls = ['http://httpbin.org/bytes/2000000',
            'http://httpbin.org/bytes/1000000',
            'http://httpbin.org/bytes/3000000']

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        # Start the load operations and mark each future with its URL
        future_to_url = {executor.submit(download_worker, url, output): url for url in urls}
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                data = future.result()
            except Exception as exc:
                output.writeln('%r generated an exception: %s' % (url, exc))
            else:
                pass
                output.writeln('%r page is %d bytes' % (url, len(data)))

    """
    r = download(requests, output=output, verify_ssl=True,
                 url='http://httpbin.org/bytes/12000', file_path=None, auth=None, retry=2,
                 retry_wait=0, overwrite=True, headers=None)
    output.info("Done!")
    """
