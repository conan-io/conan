import unittest
import uuid

from conans.util import encrypt


class EncryptTestCase(unittest.TestCase):

    def test_encryp_basic(self):
        key = str(uuid.uuid4())
        message = 'simple data ascii string'

        data = encrypt.encode(message, key)
        self.assertNotEqual(message, data)
        self.assertEquals(message, encrypt.decode(data, key))

    def test_encrypt_unicode(self):
        key = str(uuid.uuid4())
        message_enc = b'espa\xc3\xb1a\xe2\x82\xac$'  # Conan codebase allows only ASCII source files
        message = message_enc.decode('utf-8')

        data = encrypt.encode(message, key)
        self.assertNotEqual(message, data)
        self.assertEquals(message, encrypt.decode(data, key))
