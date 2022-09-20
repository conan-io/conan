import os
import re
import tempfile
import unittest

import pytest

from conans.client.downloaders.file_downloader import FileDownloader
from conans.errors import ConanException
from conans.test.utils.mocks import TestBufferConanOutput
from conans.util.files import load


class _ConfigMock:
    def __init__(self):
        self.retry = 0
        self.retry_wait = 0


class MockResponse(object):
    def __init__(self, data, headers, status_code=200):
        self.data = data
        self.ok = True
        self.status_code = status_code
        self.headers = headers.copy()
        self.headers.update({key.lower(): value for key, value in headers.items()})

    def iter_content(self, size):
        for i in range(0, len(self.data), size):
            yield self.data[i:i + size]

    def close(self):
        pass


class MockRequester(object):
    retry = 0
    retry_wait = 0

    def __init__(self, data, chunk_size=None, accept_ranges=True, echo_header=None):
        self._data = data
        self._chunk_size = chunk_size if chunk_size is not None else len(data)
        self._accept_ranges = accept_ranges
        self._echo_header = echo_header.copy() if echo_header else {}

    def get(self, *_args, **kwargs):
        start = 0
        headers = kwargs.get("headers") or {}
        transfer_range = headers.get("range", "")
        match = re.match(r"bytes=([0-9]+)-", transfer_range)
        status = 200
        headers = {"Content-Length": len(self._data), "Accept-Ranges": "bytes"}
        if match and self._accept_ranges:
            start = int(match.groups()[0])
            if start < len(self._data):
                status = 206
                headers.update({"Content-Length": str(len(self._data) - start),
                                "Content-Range": "bytes {}-{}/{}".format(start, len(self._data) - 1,
                                                                         len(self._data))})
            else:
                status = 416
                headers.update({"Content-Length": "0",
                                "Content-Range": "bytes */{}".format(len(self._data))})
        else:
            headers.update(self._echo_header)
        response = MockResponse(self._data[start:start + self._chunk_size], status_code=status,
                                headers=headers)
        return response


class DownloaderUnitTest(unittest.TestCase):
    def setUp(self):
        d = tempfile.mkdtemp()
        self.target = os.path.join(d, "target")
        self.out = TestBufferConanOutput()

    def test_succeed_download_to_file_if_not_interrupted(self):
        expected_content = b"some data"
        requester = MockRequester(expected_content)
        downloader = FileDownloader(requester=requester, output=self.out, verify=None,
                                    config_retry=0, config_retry_wait=0)
        downloader.download("fake_url", file_path=self.target)
        actual_content = load(self.target, binary=True)
        self.assertEqual(expected_content, actual_content)

    def test_succeed_download_to_memory_if_not_interrupted(self):
        expected_content = b"some data"
        requester = MockRequester(expected_content)
        downloader = FileDownloader(requester=requester, output=self.out, verify=None,
                                    config_retry=0, config_retry_wait=0)
        actual_content = downloader.download("fake_url", file_path=None)
        self.assertEqual(expected_content, actual_content)

    def test_resume_download_to_file_if_interrupted(self):
        expected_content = b"some data"
        requester = MockRequester(expected_content, chunk_size=4)
        downloader = FileDownloader(requester=requester, output=self.out, verify=None,
                                    config_retry=0, config_retry_wait=0)
        downloader.download("fake_url", file_path=self.target)
        actual_content = load(self.target, binary=True)
        self.assertEqual(expected_content, actual_content)

    def test_fail_download_to_memory_if_interrupted(self):
        expected_content = b"some data"
        requester = MockRequester(expected_content, chunk_size=4)
        downloader = FileDownloader(requester=requester, output=self.out, verify=None,
                                    config_retry=0, config_retry_wait=0)
        with pytest.raises(ConanException, match=r"Transfer interrupted before complete"):
            downloader.download("fake_url", file_path=None)

    def test_fail_interrupted_download_to_file_if_no_progress(self):
        expected_content = b"some data"
        requester = MockRequester(expected_content, chunk_size=0)
        downloader = FileDownloader(requester=requester, output=self.out, verify=None,
                                    config_retry=0, config_retry_wait=0)
        with pytest.raises(ConanException, match=r"Download failed"):
            downloader.download("fake_url", file_path=self.target)

    def test_fail_interrupted_download_if_server_not_accepting_ranges(self):
        expected_content = b"some data"
        requester = MockRequester(expected_content, chunk_size=4, accept_ranges=False)
        downloader = FileDownloader(requester=requester, output=self.out, verify=None,
                                    config_retry=0, config_retry_wait=0)
        with pytest.raises(ConanException, match=r"Incorrect Content-Range header"):
            downloader.download("fake_url", file_path=self.target)

    def test_download_with_compressed_content_and_bigger_content_length(self):
        expected_content = b"some data"
        echo_header = {"Content-Encoding": "gzip", "Content-Length": len(expected_content) + 1}
        requester = MockRequester(expected_content, echo_header=echo_header)
        downloader = FileDownloader(requester=requester, output=self.out, verify=None,
                                    config_retry=0, config_retry_wait=0)
        downloader.download("fake_url", file_path=self.target)
        actual_content = load(self.target, binary=True)
        self.assertEqual(expected_content, actual_content)

    def test_download_with_compressed_content_and_smaller_content_length(self):
        expected_content = b"some data"
        echo_header = {"Content-Encoding": "gzip", "Content-Length": len(expected_content) - 1}
        requester = MockRequester(expected_content, echo_header=echo_header)
        downloader = FileDownloader(requester=requester, output=self.out, verify=None,
                                    config_retry=0, config_retry_wait=0)
        downloader.download("fake_url", file_path=self.target)
        actual_content = load(self.target, binary=True)
        self.assertEqual(expected_content, actual_content)
