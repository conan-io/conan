import os
from conans.util.files import load
from conans.util.sha import sha1


def _normalize_crlfs(path):
    contents = load(path, binary=True)
    return contents.replace(b'\r\n', b'\n').replace(b'\r', b'\n')


def _get_file_digest(path):
    return sha1(_normalize_crlfs(path))


def get_normalized_hash(folder):
    paths = []
    for root, _, files in os.walk(folder):
        for name in files:
            if not name.endswith(".pyc"):
                paths.append(os.path.join(root, name))
    paths = sorted(paths)
    print("********** SORTED**********")
    print(paths)
    print("***************************")
    digest_lines = "\n".join([_get_file_digest(path) for path in paths])
    return sha1(digest_lines.encode("utf-8"))
