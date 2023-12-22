import hashlib
import os

from conans.errors import ConanException


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


def _generic_algorithm_sum(file_path, algorithm_name):

    with open(file_path, 'rb') as fh:
        try:
            m = hashlib.new(algorithm_name)
        except ValueError:  # FIPS error https://github.com/conan-io/conan/issues/7800
            m = hashlib.new(algorithm_name, usedforsecurity=False)
        while True:
            data = fh.read(8192)
            if not data:
                break
            m.update(data)
        return m.hexdigest()


def check_with_algorithm_sum(algorithm_name, file_path, signature):
    real_signature = _generic_algorithm_sum(file_path, algorithm_name)
    if real_signature != signature.lower():
        raise ConanException("%s signature failed for '%s' file. \n"
                             " Provided signature: %s  \n"
                             " Computed signature: %s" % (algorithm_name,
                                                          os.path.basename(file_path),
                                                          signature,
                                                          real_signature))
