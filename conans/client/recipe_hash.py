import os
from conans.util.files import load
from conans.util.sha import sha1


def normalize_crlfs(path):
    contents = load(path, binary=True)
    return contents.replace(b'\r\n', b'\n').replace(b'\r', b'\n')


def get_file_digest(path):
    return sha1(normalize_crlfs(path))


def get_normalized_hash(folder):
    paths = []
    for root, _, files in os.walk(folder):
        for name in files:
            paths.append(os.path.join(root, name))
    paths = sorted(paths)
    digest_lines = "\n".join([get_file_digest(path) for path in paths])
    return sha1(digest_lines.encode("utf-8"))
