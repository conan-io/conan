import tempfile
import unittest
from collections import namedtuple

import six

from conans.client.rest.uploader_downloader import FileUploader
from conans.errors import AuthenticationException, ForbiddenException
from conans.test.utils.tools import TestBufferConanOutput
from conans.util.files import save


class UploaderUnitTest(unittest.TestCase):

    def test_401_raises_unauthoirzed_exception(self):

        class MockRequester(object):
            retry = 0
            retry_wait = 0

            def put(self, *args, **kwargs):
                return namedtuple("response", "status_code content")(401, "tururu")

        out = TestBufferConanOutput()
        uploader = FileUploader(MockRequester(), out, verify=False)
        f = tempfile.mktemp()
        save(f, "some contents")
        with six.assertRaisesRegex(self, AuthenticationException, "tururu"):
            uploader.upload("fake_url", f)

    def test_403_raises_unauthoirzed_exception_if_no_token(self):

        class MockRequester(object):
            retry = 0
            retry_wait = 0

            def put(self, *args, **kwargs):
                return namedtuple("response", "status_code content")(403, "tururu")

        out = TestBufferConanOutput()
        auth = namedtuple("auth", "token")(None)
        uploader = FileUploader(MockRequester(), out, verify=False)
        f = tempfile.mktemp()
        save(f, "some contents")
        with six.assertRaisesRegex(self, AuthenticationException, "tururu"):
            uploader.upload("fake_url", f, auth=auth)

    def test_403_raises_forbidden_exception_if_token(self):

        class MockRequester(object):
            retry = 0
            retry_wait = 0

            def put(self, *args, **kwargs):
                return namedtuple("response", "status_code content")(403, "tururu")

        out = TestBufferConanOutput()
        auth = namedtuple("auth", "token")("SOMETOKEN")
        uploader = FileUploader(MockRequester(), out, verify=False)
        f = tempfile.mktemp()
        save(f, "some contents")
        with six.assertRaisesRegex(self, ForbiddenException, "tururu"):
            uploader.upload("fake_url", f, auth=auth)
