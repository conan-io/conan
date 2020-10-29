import unittest
import uuid

from conans.util import encrypt


class EncryptTestCase(unittest.TestCase):

    def test_encryp_basic(self):
        key = str(uuid.uuid4())
        message = 'simple data ascii string'

        data = encrypt.encode(message, key)
        self.assertEqual(type(message), type(data))
        self.assertNotEqual(message, data)

        decoded = encrypt.decode(data, key)
        self.assertEqual(type(message), type(decoded))
        self.assertEquals(message, decoded)

    def test_encrypt_unicode(self):
        key = str(uuid.uuid4())
        message_enc = b'espa\xc3\xb1a\xe2\x82\xac$'  # Conan codebase allows only ASCII source files
        message = message_enc.decode('utf-8')

        data = encrypt.encode(message, key)
        self.assertEqual(type(message), type(data))
        self.assertNotEqual(message, data)

        decoded = encrypt.decode(data, key)
        self.assertEqual(type(message), type(decoded))
        self.assertEquals(message, decoded)

    def test_key_unicode(self):
        key = b'espa\xc3\xb1a\xe2\x82\xac$'.decode('utf-8')  # codebase allows only ASCII files
        message = 'the message'

        data = encrypt.encode(message, key)
        self.assertEqual(type(message), type(data))
        self.assertNotEqual(message, data)

        decoded = encrypt.decode(data, key)
        self.assertEqual(type(message), type(decoded))
        self.assertEquals(message, decoded)

    def test_key_empty(self):
        # Empty keys, or keys with only non-ascii chars are not allowed
        with self.assertRaises(AssertionError):
            encrypt.encode('message', '')

        with self.assertRaises(AssertionError):
            encrypt.encode('message', b'\xc3\xb1\xe2\x82\xac'.decode('utf-8'))
