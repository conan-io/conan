import hashlib


def sha1(value):
    md = hashlib.sha1()
    md.update(value)
    return md.hexdigest()
