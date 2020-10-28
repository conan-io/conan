from base64 import urlsafe_b64encode, urlsafe_b64decode


# WARNING: These are useful functions to obfuscate some data, but they are NO WAY OK FOR SECURITY!

def encode(data, key):
    assert isinstance(data, str), "Expected 'str', got '{}'".format(type(data))
    return urlsafe_b64encode(bytes(key + data, 'utf-8'))


def decode(enc, key):
    assert isinstance(enc, bytes), "Expected 'bytes', got '{}'".format(type(enc))
    return urlsafe_b64decode(enc)[len(key):].decode('utf-8')
