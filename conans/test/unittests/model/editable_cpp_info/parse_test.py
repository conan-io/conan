# coding=utf-8

import textwrap
import unittest

from conans.model.editable_cpp_info import EditableCppInfo
from conans.errors import ConanException


class ParseTest(unittest.TestCase):

    def field_error_test(self):
        content = textwrap.dedent("""
                            [includedrs]
                            something
                            """)
        with self.assertRaisesRegexp(ConanException, "Wrong cpp_info field: includedrs"):
            _ = EditableCppInfo.loads(content, allow_package_name=False)
        content = textwrap.dedent("""
                            [*:includedrs]
                            something
                            """)
        with self.assertRaisesRegexp(ConanException, "Wrong cpp_info field: includedrs"):
            _ = EditableCppInfo.loads(content, allow_package_name=True)

    def namespace_error_test(self):
        content = textwrap.dedent("""
                            [*:includedirs]
                            something
                            """)
        with self.assertRaisesRegexp(ConanException, "Repository layout file doesn't allow pattern"):
            _ = EditableCppInfo.loads(content, allow_package_name=False)
