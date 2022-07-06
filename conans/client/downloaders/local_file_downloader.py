import os
from urllib.parse import urlparse
from urllib.request import url2pathname
from shutil import copyfile

from conans.client.tools.files import check_md5, check_sha1, check_sha256
from conans.errors import ConanException


class LocalFileDownloader(object):

    def __init__(self, output):
        self._output = output

    def download(self, url, file_path, md5=None, sha1=None, sha256=None, **kwargs):

        file_origin = self._path_from_file_uri(url)
        copyfile(file_origin, file_path)

        if md5:
            check_md5(file_path, md5)
        if sha1:
            check_sha1(file_path, sha1)
        if sha256:
            check_sha256(file_path, sha256)

    def _path_from_file_uri(self, uri):
       path = urlparse(uri).path
       return url2pathname(path)
