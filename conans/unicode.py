import six
import os


if six.PY2:
    get_cwd = os.getcwdu
else:
    get_cwd = os.getcwd


def make_byte_str(v, encoding=None):
    if six.PY3:
        if isinstance(v, str):
            return v.encode(encoding)
    elif isinstance(v, unicode):
        return v.encode(encoding)
    return v


def make_unicode(v):
    if six.PY2:
        if isinstance(v, str):
            return v.decode("utf8")
    elif isinstance(v, bytes):
        return v.decode("utf8")
    return v


def assert_unicode(v):
    if six.PY2:
        assert isinstance(v, unicode)
    else:
        assert isinstance(v, str)
