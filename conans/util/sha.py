import hashlib


def sha1(value):
    if value is None:
        return None
    md = hashlib.sha1()
    md.update(value)
    return md.hexdigest()
