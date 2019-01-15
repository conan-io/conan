# coding=utf-8

import unittest

from conans.client.conf import default_settings_yml
from conans.model.editable_cpp_info import EditableCppInfo
from conans.model.settings import Settings


class WorkOnItemsTest(unittest.TestCase):

    def test_empty(self):
        self.assertEqual("", EditableCppInfo._work_on_item("", None, None))

    def test_placeholders(self):
        settings = Settings.loads(default_settings_yml)
        settings.compiler = 'Visual Studio'
        settings.compiler.version = '14'
        settings.build_type = 'Debug'

        self.assertEqual('src/Visual Studio14/Debug/include',
                         EditableCppInfo._work_on_item("src/{settings.compiler}{settings.compiler.version}/{settings.build_type}/include",
                                                       settings=settings,
                                                       options=None))
        self.assertEqual('C:/Visual Studio/include/',
                         EditableCppInfo._work_on_item("C:\\{settings.compiler}\\include\\",
                                                       settings=settings,
                                                       options=None))
        self.assertEqual('C:/Visual Studio/include/',
                         EditableCppInfo._work_on_item("C:\{settings.compiler}\include\\",
                                                       settings=settings,
                                                       options=None))
        self.assertEqual('/usr/path with spaces/Visual Studio/dir',
                         EditableCppInfo._work_on_item("/usr/path with spaces/{settings.compiler}/dir",
                                                       settings=settings,
                                                       options=None))
