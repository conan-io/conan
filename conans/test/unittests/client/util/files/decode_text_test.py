# -*- coding: utf-8 -*-

import unittest

from parameterized import parameterized

from conans.util.files import decode_text


class DecodeTextTest(unittest.TestCase):

    @parameterized.expand([(b'\x41',),
                           (b'\xef\xbb\xbf\x41',),
                           (b'\xfe\xff\x00\x41',),
                           (b'\xff\xfe\x41\x00',),
                           (b'\x00\x00\xfe\xff\x00\x00\x00\x41',),
                           (b'\xff\xfe\x00\x00\x41\x00\x00\x00',),
                           (b'\x2b\x2f\x76\x38\x41',),
                           (b'\x2b\x2f\x76\x39\x41',),
                           (b'\x2b\x2f\x76\x2B\x41',),
                           (b'\x2b\x2f\x76\x2F\x41',),
                           (b'\x2b\x2f\x76\x38\x2d\x41',)])
    def test_encodings(self, text):
        self.assertEqual('A', decode_text(text))
