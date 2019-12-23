import tempfile
import unittest
from collections import namedtuple

import six

from conans.client.rest.uploader_downloader import FileUploader
from conans.errors import AuthenticationException, ForbiddenException
from conans.test.utils.tools import TestBufferConanOutput
from conans.util.files import save


class _ConfigMock:
    def __init__(self):
        self.retry = 0
        self.retry_wait = 0


class _MockRequester(object):
    def __init__(self, code):
        self._code = code

    def put(self, *args, **kwargs):
        return namedtuple("response", "status_code content")(self._code, "tururu")


class UploaderUnitTest(unittest.TestCase):

    def test_401_raises_unauthoirzed_exception(self):
        out = TestBufferConanOutput()
        uploader = FileUploader(_MockRequester(401), out, verify=False, config=_ConfigMock())
        f = tempfile.mktemp()
        save(f, "some contents")
        with six.assertRaisesRegex(self, AuthenticationException, "tururu"):
            uploader.upload("fake_url", f)

    def test_403_raises_unauthoirzed_exception_if_no_token(self):
        out = TestBufferConanOutput()
        auth = namedtuple("auth", "token")(None)
        uploader = FileUploader(_MockRequester(403), out, verify=False, config=_ConfigMock())
        f = tempfile.mktemp()
        save(f, "some contents")
        with six.assertRaisesRegex(self, AuthenticationException, "tururu"):
            uploader.upload("fake_url", f, auth=auth)

    def test_403_raises_forbidden_exception_if_token(self):
        out = TestBufferConanOutput()
        auth = namedtuple("auth", "token")("SOMETOKEN")
        uploader = FileUploader(_MockRequester(403), out, verify=False, config=_ConfigMock())
        f = tempfile.mktemp()
        save(f, "some contents")
        with six.assertRaisesRegex(self, ForbiddenException, "tururu"):
            uploader.upload("fake_url", f, auth=auth)
