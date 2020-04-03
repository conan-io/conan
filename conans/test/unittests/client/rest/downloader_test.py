import re
import tempfile
import unittest

import six

from conans.client.rest.file_downloader import FileDownloader
from conans.test.utils.tools import TestBufferConanOutput
from conans.util.files import load


class _ConfigMock:
    def __init__(self):
        self.retry = 0
        self.retry_wait = 0


class MockResponse(object):
    def __init__(self, data, transfer_size=None):
        self.data = data
        self.ok = True
        self.status_code = 200
        self.start = 0
        self.size = len(self.data)
        self.transfer_size = transfer_size or self.size
        assert self.transfer_size <= self.size
        self.headers = {"content-length": self.size, "content-encoding": "gzip",
                        "accept-ranges": "bytes"}

    def iter_content(self, size):
        transfer_size = min(size, self.transfer_size)
        pos = self.start
        if pos >= len(self.data):
            yield six.b("")
        yield self.data[pos:pos + transfer_size]
        pos += transfer_size

    def close(self):
        pass


class MockRequester(object):
    retry = 0
    retry_wait = 0

    def __init__(self, response):
        self._response = response

    def get(self, *_args, **kwargs):
        headers = kwargs.get("headers") or {}
        transfer_range = headers.get("range", "")
        match = re.match(r"bytes=([0-9]+)-", transfer_range)
        if match:
            start = int(match.groups()[0])
            assert start <= self._response.size
            self._response.start = start

        return self._response


class DownloaderUnitTest(unittest.TestCase):
    def setUp(self):
        self.target = tempfile.mktemp()
        self.out = TestBufferConanOutput()

    def test_download_file_ok(self):
        expected_content = six.b("some data")
        requester = MockRequester(MockResponse(expected_content))
        downloader = FileDownloader(requester=requester, output=self.out, verify=None,
                                    config=_ConfigMock())
        downloader.download("fake_url", file_path=self.target)
        actual_content = load(self.target, binary=True)
        self.assertEqual(expected_content, actual_content)

    def test_download_file_interrupted(self):
        expected_content = six.b("some data")
        requester = MockRequester(MockResponse(expected_content, transfer_size=4))
        downloader = FileDownloader(requester=requester, output=self.out, verify=None,
                                    config=_ConfigMock())
        downloader.download("fake_url", file_path=self.target)
        actual_content = load(self.target, binary=True)
        self.assertEqual(expected_content, actual_content)
