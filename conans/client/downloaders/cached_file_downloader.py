import os
import shutil
from contextlib import contextmanager
from threading import Lock

from conans.client.downloaders.file_downloader import check_checksum
from conans.client.downloaders.utils import hash_url
from conans.errors import ConanException
from conans.util.files import mkdir
from conans.util.locks import SimpleLock


class CachedFileDownloader(object):
    _thread_locks = {}  # Needs to be shared among all instances
    _cache_mapping = '.cached_files'

    def __init__(self, cache_folder, file_downloader, user_download=False):
        self._cache_folder = cache_folder
        self._file_downloader = file_downloader
        self._user_download = user_download

    @contextmanager
    def _lock(self, lock_id):
        lock = os.path.join(self._cache_folder, "locks", lock_id)
        with SimpleLock(lock):
            # Once the process has access, make sure multithread is locked too
            # as SimpleLock doesn't work multithread
            thread_lock = self._thread_locks.setdefault(lock, Lock())
            thread_lock.acquire()
            try:
                yield
            finally:
                thread_lock.release()

    def download(self, url, file_path=None, md5=None, sha1=None, sha256=None, **kwargs):
        """ compatible interface of FileDownloader + checksum
        """
        checksum = sha256 or sha1 or md5
        # If it is a user download, it must contain a checksum
        assert (not self._user_download) or (self._user_download and checksum)
        h = hash_url(url, checksum, self._user_download)

        with self._lock(h):
            cached_path = os.path.join(self._cache_folder, h)
            if not os.path.exists(cached_path):
                self._file_downloader.download(url=url, file_path=cached_path, md5=md5,
                                               sha1=sha1, sha256=sha256, **kwargs)
                with self._lock(self._cache_mapping):
                    mapping_filename = os.path.join(self._cache_folder, self._cache_mapping)
                    with open(mapping_filename, "a") as f:
                        f.write("{}: {}\n".format(h, url))
            else:
                # specific check for corrupted cached files, will raise, but do nothing more
                # user can report it or "rm -rf cache_folder/path/to/file"
                try:
                    check_checksum(cached_path, md5, sha1, sha256)
                except ConanException as e:
                    raise ConanException("%s\nCached downloaded file corrupted: %s"
                                         % (str(e), cached_path))

            if file_path is not None:
                file_path = os.path.abspath(file_path)
                mkdir(os.path.dirname(file_path))
                shutil.copy2(cached_path, file_path)
            else:
                with open(cached_path, 'rb') as handle:
                    tmp = handle.read()
                return tmp
