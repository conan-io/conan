import tempfile
import unittest
from collections import namedtuple

import six

from conans.client.rest.file_uploader import FileUploader
from conans.errors import AuthenticationException, ForbiddenException, InternalErrorException
from conans.test.utils.mocks import TestBufferConanOutput
from conans.util.files import save


class _ConfigMock:
    def __init__(self):
        self.retry = 0
        self.retry_wait = 0


class MockRequester(object):
    retry = 0
    retry_wait = 0

    def __init__(self, response):
        self._response = response

    def put(self, *args, **kwargs):
        return namedtuple("response", "status_code content")(self._response, "tururu")


class UploaderUnitTest(unittest.TestCase):
    def setUp(self):
        _, self.f = tempfile.mkstemp()
        save(self.f, "some contents")
        self.out = TestBufferConanOutput()

    def test_401_raises_unauthoirzed_exception(self):
        uploader = FileUploader(MockRequester(401), self.out, verify=False, config=_ConfigMock())
        with six.assertRaisesRegex(self, AuthenticationException, "tururu"):
            uploader.upload("fake_url", self.f)

    def test_403_raises_unauthoirzed_exception_if_no_token(self):
        auth = namedtuple("auth", "token")(None)
        uploader = FileUploader(MockRequester(403), self.out, verify=False, config=_ConfigMock())
        with six.assertRaisesRegex(self, AuthenticationException, "tururu"):
            uploader.upload("fake_url", self.f, auth=auth)

    def test_403_raises_unauthorized_exception_if_no_auth(self):
        uploader = FileUploader(MockRequester(403), self.out, verify=False, config=_ConfigMock())
        with six.assertRaisesRegex(self, AuthenticationException, "tururu"):
            uploader.upload("fake_url", self.f)

    def test_403_raises_forbidden_exception_if_token(self):
        auth = namedtuple("auth", "token")("SOMETOKEN")
        uploader = FileUploader(MockRequester(403), self.out, verify=False, config=_ConfigMock())
        with six.assertRaisesRegex(self, ForbiddenException, "tururu"):
            uploader.upload("fake_url", self.f, auth=auth)

    def test_500_raises_internal_error(self):
        out = TestBufferConanOutput()
        uploader = FileUploader(MockRequester(500), out, verify=False, config=_ConfigMock())
        _, f = tempfile.mkstemp()
        save(f, "some contents")
        with six.assertRaisesRegex(self, InternalErrorException, "tururu"):
            uploader.upload("fake_url", self.f, dedup=True)
