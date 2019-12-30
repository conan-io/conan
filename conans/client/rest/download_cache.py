import os
import shutil
from urlparse import urlsplit, urljoin

from conans.util.files import mkdir
from conans.util.locks import SimpleLock
from conans.util.sha import sha256


class CachedFileDownloader(object):

    def __init__(self, cache_folder, file_downloader):
        self._cache_folder = cache_folder
        self._file_downloader = file_downloader

    def download(self, url, file_path=None, auth=None, retry=None, retry_wait=None, overwrite=False,
                 headers=None, checksum=None):
        """ compatible interface + checksum
        """
        h = self._get_hash(url, checksum)
        lock = os.path.join(self._cache_folder, "locks", h)
        cached_path = os.path.join(self._cache_folder, h)
        with SimpleLock(lock):
            if not os.path.exists(cached_path):
                self._file_downloader.download(url, cached_path, auth, retry, retry_wait,
                                               overwrite, headers)
            if file_path is not None:
                mkdir(os.path.dirname(file_path))
                shutil.copy2(cached_path, file_path)
            else:
                with open(cached_path, 'rb') as handle:
                    tmp = handle.read()
                return tmp

    @staticmethod
    def _get_hash(url, checksum=None):
        urltokens = urlsplit(url)
        url = urljoin(*urltokens[0:2])
        if checksum is not None:
            url += checksum
        h = sha256(url)
        return h

