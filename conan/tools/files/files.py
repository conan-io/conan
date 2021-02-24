from conans.util.files import load as util_load, save as files_save, save_append, mkdir as util_mkdir
from conans.client.tools.net import ftp_download as util_ftp_download, download as util_download, \
     get as util_get


def load(conanfile, path, binary=False, encoding="auto"):
    util_load(path, binary=binary, encoding=encoding)


def save(conanfile, path, content, append=False):
    # TODO: All this three functions: save, save_append and this one should be merged into one.
    if append:
        save_append(path=path, content=content)
    else:
        files_save(path=path, content=content, only_if_modified=False)


def mkdir(conanfile, path):
    util_mkdir(path)


def ftp_download(conanfile, ip, filename, login='', password=''):
    return util_ftp_download(ip, filename, login=login, password=password)


def download(conanfile, *args, **kwargs):
    return util_download(out=conanfile.output, requester=conanfile._requester, *args, **kwargs)


def get(conanfile, *args, **kwargs):
    return util_get(output=conanfile.output, requester=conanfile._requester, *args, **kwargs)
