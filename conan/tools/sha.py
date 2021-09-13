import hashlib


def sha256(value):
    if value is None:
        return None
    md = hashlib.sha256()
    md.update(value)
    return md.hexdigest()
