import uuid

import pytest

from conan.internal.api.remotes import encrypt


def test_encryp_basic():
    key = str(uuid.uuid4())
    message = 'simple data ascii string'

    data = encrypt.encode(message, key)
    assert type(message) == type(data)
    assert message != data
    assert message != data

    decoded = encrypt.decode(data, key)
    assert type(message) == type(data)
    assert message == decoded


def test_encrypt_unicode():
    key = str(uuid.uuid4())
    message_enc = b'espa\xc3\xb1a\xe2\x82\xac$'  # Conan codebase allows only ASCII source files
    message = message_enc.decode('utf-8')

    data = encrypt.encode(message, key)
    assert type(message) == type(data)
    assert message != data

    decoded = encrypt.decode(data, key)
    assert type(message) == type(data)
    assert message == decoded


def test_key_unicode():
    key = b'espa\xc3\xb1a\xe2\x82\xac$'.decode('utf-8')  # codebase allows only ASCII files
    message = 'the message'

    data = encrypt.encode(message, key)
    assert type(message) == type(data)
    assert message != data

    decoded = encrypt.decode(data, key)
    assert type(message) == type(data)
    assert message == decoded


def test_key_empty():
    # Empty keys, or keys with only non-ascii chars are not allowed
    with pytest.raises(AssertionError):
        encrypt.encode('message', '')

    with pytest.raises(AssertionError):
        encrypt.encode('message', b'\xc3\xb1\xe2\x82\xac'.decode('utf-8'))
