import os
import shutil

from conans.util.files import mkdir
from conans.util.locks import SimpleLock
from conans.util.sha import sha256


class CachedFileDownloader(object):

    def __init__(self, cache_folder, file_downloader):
        self._cache_folder = cache_folder
        self._file_downloader = file_downloader

    def download(self, url, file_path=None, auth=None, retry=None, retry_wait=None, overwrite=False,
                 headers=None):
        """ compatible interface
        """
        cached_path = self._get_path(url)
        with SimpleLock(cached_path + ".lock"):
            if not os.path.exists(cached_path):
                print "NOT CACHED; DOWNLOADING ", url
                self._file_downloader.download(url, cached_path, auth, retry, retry_wait,
                                               overwrite, headers)
            else:
                print "USING CACHED VERSION OF ", url
            if file_path is not None:
                mkdir(os.path.dirname(file_path))
                shutil.copy2(cached_path, file_path)
            else:
                with open(cached_path, 'rb') as handle:
                    tmp = handle.read()
                return tmp

    def _get_path(self, url, checksum=None):
        if checksum is not None:
            url += checksum
        h = sha256(url)
        p = os.path.join(self._cache_folder, h)
        return p

