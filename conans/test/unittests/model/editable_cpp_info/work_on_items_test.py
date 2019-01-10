# coding=utf-8

import os
import unittest

from parameterized import parameterized

from conans.client.conf import default_settings_yml
from conans.model.editable_cpp_info import EditableCppInfo
from conans.model.settings import Settings


def _make_abs(base_path, *args):
    p = os.path.join(*args)
    if base_path:
        p = os.path.join(base_path, p)
        p = os.path.abspath(p)
    return p


class WorkOnItemsTest(unittest.TestCase):

    def test_empty(self):
        self.assertEqual(".", EditableCppInfo._work_on_item("", None, None, None))

    @parameterized.expand([(False,), (True,)])
    def test_basic(self, make_abs):
        base_path = os.path.dirname(__file__) if make_abs else None

        self.assertIn(_make_abs(base_path, '.'),
                      EditableCppInfo._work_on_item(".", base_path, None, None))
        self.assertIn(_make_abs(base_path, 'src', 'include'),
                      EditableCppInfo._work_on_item("src/include", base_path, None, None))
        self.assertIn(_make_abs(base_path, '..', 'relative', 'include'),
                      EditableCppInfo._work_on_item("../relative/include", base_path, None, None))
        self.assertIn(_make_abs(base_path, 'src', 'path with spaces', 'include'),
                      EditableCppInfo._work_on_item("src/path with spaces/include",
                                                    base_path, None, None))
        self.assertIn(_make_abs(base_path, 'ending-slash', 'include'),
                      EditableCppInfo._work_on_item("ending-slash/include/", base_path, None, None))

    @parameterized.expand([(False,), (True,)])
    def test_windows(self, make_abs):
        base_path = os.path.dirname(__file__) if make_abs else None

        self.assertIn(os.path.join('C:' + os.sep, 'Windows-single-slash', 'include'),
                      EditableCppInfo._work_on_item("C:\Windows-single-slash\include",
                                                    base_path, None, None))
        self.assertIn(os.path.join('D:' + os.sep, 'Windows-double-slash', 'include'),
                      EditableCppInfo._work_on_item("D:\\Windows-double-slash\\include",
                                                    base_path, None, None))

    @parameterized.expand([(False,), (True,)])
    def test_unix(self, make_abs):
        base_path = os.path.dirname(__file__) if make_abs else None

        self.assertIn(os.path.join(os.sep, 'abs', 'path', 'include'),
                      EditableCppInfo._work_on_item("/abs/path/include", base_path, None, None))

    @parameterized.expand([(False,), (True,)])
    def test_placeholders(self, make_abs):
        base_path = os.path.dirname(__file__) if make_abs else None

        settings = Settings.loads(default_settings_yml)
        settings.compiler = 'Visual Studio'
        settings.compiler.version = '14'
        settings.build_type = 'Debug'

        self.assertIn(_make_abs(base_path, 'src', 'Visual Studio14', 'Debug', 'include'),
                      EditableCppInfo._work_on_item("src/{settings.compiler}{settings.compiler.version}/{settings.build_type}/include",
                                                    base_path=base_path, settings=settings,
                                                    options=None))
        self.assertIn(os.path.join('C:' + os.sep, 'Visual Studio', 'include'),
                      EditableCppInfo._work_on_item("C:\\{settings.compiler}\\include\\",
                                                    base_path=base_path, settings=settings,
                                                    options=None))
        self.assertIn(os.path.join(os.sep, 'usr', 'path with spaces', 'Visual Studio', 'dir'),
                      EditableCppInfo._work_on_item("/usr/path with spaces/{settings.compiler}/dir",
                                                    base_path=base_path, settings=settings,
                                                    options=None))
