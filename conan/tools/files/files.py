from conans.util.files import load as util_load


def load(conanfile, path, binary=False, encoding="auto"):
    util_load(path, binary=binary, encoding=encoding)
