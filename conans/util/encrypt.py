from base64 import urlsafe_b64encode, urlsafe_b64decode

import six


# WARNING: These are useful functions to obfuscate some data, but they are NO WAY OK FOR SECURITY!

def encode(data, key):
    assert isinstance(data, six.string_types), "Expected string type, got '{}'".format(type(data))
    if six.PY3:
        return urlsafe_b64encode(bytes(key + data, 'utf-8'))
    else:
        return urlsafe_b64encode(str(key + data).encode('utf-8'))


def decode(enc, key):
    assert isinstance(enc, bytes), "Expected 'bytes', got '{}'".format(type(enc))
    return urlsafe_b64decode(enc)[len(key):].decode('utf-8')
