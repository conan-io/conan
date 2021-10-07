import os
import shutil
from contextlib import contextmanager
from threading import Lock

from six.moves.urllib_parse import urlsplit, urlunsplit

from conans.client.downloaders.file_downloader import check_checksum
from conans.errors import ConanException
from conans.util.log import logger
from conans.util.files import mkdir, set_dirty, clean_dirty, is_dirty, remove
from conans.util.locks import SimpleLock
from conans.util.sha import sha256 as sha256_sum


class CachedFileDownloader(object):
    _thread_locks = {}  # Needs to be shared among all instances

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
        h = self._get_hash(url, checksum)

        with self._lock(h):
            cached_path = os.path.join(self._cache_folder, h)
            if is_dirty(cached_path):
                if os.path.exists(cached_path):
                    os.remove(cached_path)
                clean_dirty(cached_path)

            if os.path.exists(cached_path):
                # If exists but it is corrupted, it is removed. Note that v2 downloads
                # do not have checksums, this only works for user downloads
                try:
                    check_checksum(cached_path, md5, sha1, sha256)
                except ConanException:
                    logger.error("Cached file corrupt, redownloading")
                    remove(cached_path)

            if not os.path.exists(cached_path):
                set_dirty(cached_path)
                self._file_downloader.download(url=url, file_path=cached_path, md5=md5,
                                               sha1=sha1, sha256=sha256, **kwargs)
                clean_dirty(cached_path)

            if file_path is not None:
                file_path = os.path.abspath(file_path)
                mkdir(os.path.dirname(file_path))
                shutil.copy2(cached_path, file_path)
            else:
                with open(cached_path, 'rb') as handle:
                    tmp = handle.read()
                return tmp

    def _get_hash(self, url, checksum=None):
        """ For Api V2, the cached downloads always have recipe and package REVISIONS in the URL,
        making them immutable, and perfect for cached downloads of artifacts. For V2 checksum
        will always be None.
        For ApiV1, the checksum is obtained from the server via "get_snapshot()" methods, but
        the URL in the apiV1 contains the signature=xxx for signed urls, but that can change,
        so better strip it from the URL before the hash
        """
        scheme, netloc, path, _, _ = urlsplit(url)
        # append empty query and fragment before unsplit
        if not self._user_download:  # removes ?signature=xxx
            url = urlunsplit((scheme, netloc, path, "", ""))
        if checksum is not None:
            url += checksum
        h = sha256_sum(url.encode())
        return h
