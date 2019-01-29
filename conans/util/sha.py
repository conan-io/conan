import hashlib


def sha1(value):
    if value is None:
        return None
    md = hashlib.sha1()
    md.update(value)
    return md.hexdigest()


def sha256(value):
    if value is None:
        return None
    md = hashlib.sha256()
    md.update(value)
    return md.hexdigest()
