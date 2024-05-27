import os
import unittest
from collections import namedtuple, Counter

from requests.exceptions import HTTPError

from conans.client.rest.file_uploader import FileUploader
from conans.errors import AuthenticationException, ForbiddenException
from conan.test.utils.mocks import RedirectedTestOutput
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import redirect_output
from conans.util.files import save


class _ResponseMock:
    def __init__(self, status_code, content):
        self.status_code = status_code
        self.content = content

    def raise_for_status(self):
        """Raises stored :class:`HTTPError`, if one occurred."""

        http_error_msg = ''
        if 400 <= self.status_code < 500:
            http_error_msg = u'%s Client Error: %s' % (self.status_code, self.content)

        elif 500 <= self.status_code < 600:
            http_error_msg = u'%s Server Error: %s' % (self.status_code, self.content)

        if http_error_msg:
            raise HTTPError(http_error_msg, response=self)


class _RequesterMock:
    def __init__(self, status_code, content):
        self.response = _ResponseMock(status_code, content)
        self.retry = 0
        self.retry_wait = 0

    def put(self, *args, **kwargs):
        return self.response


class _ConfigMock:
    def __getitem__(self, item):
        return 0

    def get(self, conf_name, default=None, check_type=None):
        return 0


class RetryDownloadTests(unittest.TestCase):

    def setUp(self):
        self.filename = os.path.join(temp_folder(), "anyfile")
        save(self.filename, "anything")

    def test_error_401(self):
        output = RedirectedTestOutput()
        with redirect_output(output):
            uploader = FileUploader(requester=_RequesterMock(401, "content"),
                                    verify=False, config=_ConfigMock())
            with self.assertRaisesRegex(AuthenticationException, "content"):
                uploader.upload(url="fake", abs_path=self.filename, retry=2)
            output_lines = output.getvalue().splitlines()
            counter = Counter(output_lines)
            self.assertEqual(counter["ERROR: content"], 0)
            self.assertEqual(counter["Waiting 0 seconds to retry..."], 0)

    def test_error_403_forbidden(self):
        output = RedirectedTestOutput()
        with redirect_output(output):
            uploader = FileUploader(requester=_RequesterMock(403, "content"),
                                    verify=False, config=_ConfigMock())
            with self.assertRaisesRegex(ForbiddenException, "content"):
                auth = namedtuple("auth", "token")
                uploader.upload(url="fake", abs_path=self.filename, retry=2, auth=auth("token"))
            output_lines = output.getvalue().splitlines()
            counter = Counter(output_lines)
            self.assertEqual(counter["ERROR: content"], 0)
            self.assertEqual(counter["Waiting 0 seconds to retry..."], 0)

    def test_error_403_authentication(self):
        output = RedirectedTestOutput()
        with redirect_output(output):
            uploader = FileUploader(requester=_RequesterMock(403, "content"),
                                    verify=False, config=_ConfigMock())
            with self.assertRaisesRegex(AuthenticationException, "content"):
                auth = namedtuple("auth", "token")
                uploader.upload(url="fake", abs_path=self.filename, retry=2, auth=auth(None))
            output_lines = output.getvalue().splitlines()
            counter = Counter(output_lines)
            self.assertEqual(counter["ERROR: content"], 0)
            self.assertEqual(counter["Waiting 0 seconds to retry..."], 0)

    def test_error_requests(self):
        class _RequesterMock:

            def put(self, *args, **kwargs):
                raise Exception("any exception")

        output = RedirectedTestOutput()
        with redirect_output(output):
            uploader = FileUploader(requester=_RequesterMock(), verify=False, config=_ConfigMock())
            with self.assertRaisesRegex(Exception, "any exception"):
                uploader.upload(url="fake", abs_path=self.filename, retry=2)
            output_lines = output.getvalue().splitlines()
            counter = Counter(output_lines)
            self.assertEqual(counter["WARN: network: any exception"], 2)
            self.assertEqual(counter["Waiting 0 seconds to retry..."], 2)

    def test_error_500(self):
        output = RedirectedTestOutput()
        with redirect_output(output):
            uploader = FileUploader(requester=_RequesterMock(500, "content"), verify=False,
                                    config=_ConfigMock())
            with self.assertRaisesRegex(Exception, "500 Server Error: content"):
                uploader.upload(url="fake", abs_path=self.filename, retry=2)
            output_lines = output.getvalue().splitlines()
            counter = Counter(output_lines)
            self.assertEqual(counter["WARN: network: 500 Server Error: content"], 2)
            self.assertEqual(counter["Waiting 0 seconds to retry..."], 2)
