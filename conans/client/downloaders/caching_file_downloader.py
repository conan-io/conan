import os
import shutil
from contextlib import contextmanager
from threading import Lock

from conan.api.output import ConanOutput
from conans.client.downloaders.file_downloader import FileDownloader
from conans.util.files import mkdir, set_dirty_context_manager, remove_if_dirty
from conans.util.locks import SimpleLock
from conans.util.sha import sha256 as compute_sha256


class CachingFileDownloader:

    def __init__(self, requester,  download_cache):
        self._output = ConanOutput()
        self._download_cache = download_cache
        self._file_downloader = FileDownloader(requester)

    def download(self, url, file_path, retry=2, retry_wait=0, verify_ssl=True, auth=None,
                 overwrite=False, headers=None, md5=None, sha1=None, sha256=None):
        if self._download_cache:
            self._caching_download(url, file_path, retry=retry, retry_wait=retry_wait,
                                   verify_ssl=verify_ssl, auth=auth, overwrite=overwrite,
                                   headers=headers, md5=md5, sha1=sha1, sha256=sha256)
        else:
            self._file_downloader.download(url, file_path, retry=retry, retry_wait=retry_wait,
                                           verify_ssl=verify_ssl, auth=auth, overwrite=overwrite,
                                           headers=headers, md5=md5, sha1=sha1, sha256=sha256)

    _thread_locks = {}  # Needs to be shared among all instances

    @contextmanager
    def _lock(self, lock_id):
        lock = os.path.join(self._download_cache, "locks", lock_id)
        with SimpleLock(lock):
            # Once the process has access, make sure multithread is locked too
            # as SimpleLock doesn't work multithread
            thread_lock = self._thread_locks.setdefault(lock, Lock())
            thread_lock.acquire()
            try:
                yield
            finally:
                thread_lock.release()

    def _caching_download(self, url, file_path, md5, sha1, sha256, **kwargs):
        h = self._get_hash(url, md5, sha1, sha256)
        with self._lock(h):
            cached_path = os.path.join(self._download_cache, h)
            remove_if_dirty(cached_path)

            if not os.path.exists(cached_path):
                with set_dirty_context_manager(cached_path):
                    self._file_downloader.download(url=url, file_path=cached_path, md5=md5,
                                                   sha1=sha1, sha256=sha256, **kwargs)

            # Everything good, file in the cache, just copy it to final destination
            file_path = os.path.abspath(file_path)
            mkdir(os.path.dirname(file_path))
            shutil.copy2(cached_path, file_path)

    @staticmethod
    def _get_hash(url, md5, sha1, sha256):
        """ For Api V2, the cached downloads always have recipe and package REVISIONS in the URL,
        making them immutable, and perfect for cached downloads of artifacts. For V2 checksum
        will always be None.
        """
        checksum = sha256 or sha1 or md5
        if checksum is not None:
            url += checksum
        h = compute_sha256(url.encode())
        return h
