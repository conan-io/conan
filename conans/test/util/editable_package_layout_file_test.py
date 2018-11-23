# coding=utf-8

import os
import six
import unittest
from parameterized import parameterized

from conans.paths.package_layouts.package_user_layout import parse_package_layout_content


def _make_abs(base_path, *args):
    p = os.path.join(*args)
    if base_path:
        p = os.path.join(base_path, p)
        p = os.path.abspath(p)
    return p


class ParseContentExplicitTestCase(unittest.TestCase):
    content = six.u("""
[includedirs]
{includedirs_pack}

[libdirs]
[resdirs]
[bindirs]
""")

    @parameterized.expand([(False, ), (True, )])
    def test_empty(self, make_abs):
        # Always return the same dictionary if keys are empty or do not exist
        base_path = os.path.dirname(__file__) if make_abs else None
        expected = {'includedirs': [], 'libdirs': [], 'resdirs': [], 'bindirs': []}

        data = parse_package_layout_content(content=u"", base_path=base_path)
        self.assertDictEqual(data, expected)

        data = parse_package_layout_content(content=self.content.format(includedirs_pack=""),
                                            base_path=base_path)
        self.assertDictEqual(data, expected)

        data = parse_package_layout_content(content=u"[other_section]\nvalue", base_path=base_path)
        self.assertDictEqual(data, expected)

    @parameterized.expand([(False, ), (True, )])
    def test_basic(self, make_abs):
        basic_pack = """
.
src/include
../relative/include
src/path with spaces/include
ending-slash/include/
"""

        content = self.content.format(includedirs_pack=basic_pack)
        base_path = os.path.dirname(__file__) if make_abs else None

        data = parse_package_layout_content(content, base_path=base_path)
        self.assertFalse(data['libdirs'])
        self.assertFalse(data['resdirs'])
        self.assertFalse(data['bindirs'])

        includedirs = data['includedirs']
        self.assertIn(_make_abs(base_path, '.'), includedirs)
        self.assertIn(_make_abs(base_path, '.'), includedirs)
        self.assertIn(_make_abs(base_path, 'src', 'include'), includedirs)
        self.assertIn(_make_abs(base_path, '..', 'relative', 'include'), includedirs)
        self.assertIn(_make_abs(base_path, 'src', 'path with spaces', 'include'), includedirs)
        self.assertIn(_make_abs(base_path, 'ending-slash', 'include'), includedirs)

    @parameterized.expand([(False,), (True,)])
    def test_windows_pack(self, make_abs):
        windows_pack = r"""
C:\Windows-single-slash\include
D:\\Windows-double-slash\\include
"""
        content = self.content.format(includedirs_pack=windows_pack)
        base_path = os.path.dirname(__file__) if make_abs else None

        data = parse_package_layout_content(content, base_path=base_path)
        self.assertFalse(data['libdirs'])
        self.assertFalse(data['resdirs'])
        self.assertFalse(data['bindirs'])

        includedirs = data['includedirs']
        self.assertIn(os.path.join('C:' + os.sep, 'Windows-single-slash', 'include'), includedirs)
        self.assertIn(os.path.join('D:' + os.sep, 'Windows-double-slash', 'include'), includedirs)

    @parameterized.expand([(False,), (True,)])
    def test_unix_pack(self, make_abs):
        unix_pack = """
/abs/path/include
"""
        content = self.content.format(includedirs_pack=unix_pack)
        base_path = os.path.dirname(__file__) if make_abs else None

        data = parse_package_layout_content(content, base_path=base_path)
        self.assertFalse(data['libdirs'])
        self.assertFalse(data['resdirs'])
        self.assertFalse(data['bindirs'])

        includedirs = data['includedirs']
        self.assertIn(os.path.join(os.sep, 'abs', 'path', 'include'), includedirs)


class ParsePlaceholdersTestCase(unittest.TestCase):

    @parameterized.expand([(False,), (True,)])
    def test_parse_placeholders(self, make_abs):
        base_path = os.path.dirname(__file__) if make_abs else None
        content = six.u(r"""
[includedirs]
src/{compiler}{compiler.version}/{build_type}/include
C:\\{compiler}\\include\\
/usr/path with spaces/{compiler}/dir
""")
        data = parse_package_layout_content(content, base_path=base_path)
        includedirs = data['includedirs']
        self.assertIn(_make_abs(base_path, 'src', '{compiler}{compiler.version}', '{build_type}', 'include'), includedirs)
        self.assertIn(os.path.join('C:' + os.sep, '{compiler}', 'include'), includedirs)
        self.assertIn(os.path.join(os.sep, 'usr', 'path with spaces', '{compiler}', 'dir'), includedirs)


# TODO: Add tests with interpolations:
#   https://docs.python.org/3/library/configparser.html#interpolation-of-values

# TODO: Add tests with conditionals inside f-strings
