import os
import shutil

from six.moves.urllib_parse import urlsplit, urlunsplit

from conans.util.files import mkdir
from conans.util.locks import SimpleLock
from conans.util.sha import sha256


class CachedFileDownloader(object):

    def __init__(self, cache_folder, file_downloader):
        self._cache_folder = cache_folder
        self._file_downloader = file_downloader

    def download(self, url, file_path=None, auth=None, retry=None, retry_wait=None, overwrite=False,
                 headers=None, checksum=None):
        """ compatible interface of FileDownloader + checksum
        """
        h = self._get_hash(url, checksum)
        lock = os.path.join(self._cache_folder, "locks", h)
        cached_path = os.path.join(self._cache_folder, h)
        with SimpleLock(lock):
            if not os.path.exists(cached_path):
                self._file_downloader.download(url, cached_path, auth, retry, retry_wait,
                                               overwrite, headers)
            if file_path is not None:
                file_path = os.path.abspath(file_path)
                mkdir(os.path.dirname(file_path))
                shutil.copy2(cached_path, file_path)
            else:
                with open(cached_path, 'rb') as handle:
                    tmp = handle.read()
                return tmp

    @staticmethod
    def _get_hash(url, checksum=None):
        """ For Api V2, the cached downloads always have recipe and package REVISIONS in the URL,
        making them immutable, and perfect for cached downloads of artifacts. For V2 checksum
        will always be None.
        For ApiV1, the checksum is obtained from the server via "get_snapshot()" methods, but
        the URL in the apiV1 contains the signature=xxx for signed urls, but that can change,
        so better strip it from the URL before the hash
        """
        urltokens = urlsplit(url)
        # append empty query and fragment before unsplit
        url = urlunsplit(urltokens[0:3]+("", ""))
        if checksum is not None:
            url += checksum
        h = sha256(url.encode())
        return h

