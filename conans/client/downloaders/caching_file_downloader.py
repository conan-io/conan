import json
import os
import shutil
from contextlib import contextmanager
from threading import Lock

from conan.api.output import ConanOutput
from conans.client.downloaders.file_downloader import FileDownloader
from conans.client.downloaders.download_cache import DownloadCache
from conans.util.files import mkdir, set_dirty_context_manager, remove_if_dirty, load, save
from conans.util.locks import SimpleLock


class CachingFileDownloader:

    def __init__(self, requester,  download_cache):
        self._output = ConanOutput()
        self._download_cache = DownloadCache(download_cache)
        self._file_downloader = FileDownloader(requester)

    def download(self, url, file_path, retry=2, retry_wait=0, verify_ssl=True, auth=None,
                 overwrite=False, headers=None, md5=None, sha1=None, sha256=None,
                 conanfile=None):
        if self._download_cache:
            self._caching_download(url, file_path, retry=retry, retry_wait=retry_wait,
                                   verify_ssl=verify_ssl, auth=auth, overwrite=overwrite,
                                   headers=headers, md5=md5, sha1=sha1, sha256=sha256,
                                   conanfile=conanfile)
        else:
            self._file_downloader.download(url, file_path, retry=retry, retry_wait=retry_wait,
                                           verify_ssl=verify_ssl, auth=auth, overwrite=overwrite,
                                           headers=headers, md5=md5, sha1=sha1, sha256=sha256)

    _thread_locks = {}  # Needs to be shared among all instances

    @contextmanager
    def _lock(self, lock_id):
        lock = self._download_cache.get_lock_path(lock_id)
        with SimpleLock(lock):
            # Once the process has access, make sure multithread is locked too
            # as SimpleLock doesn't work multithread
            thread_lock = self._thread_locks.setdefault(lock, Lock())
            thread_lock.acquire()
            try:
                yield
            finally:
                thread_lock.release()

    def _caching_download(self, url, file_path, md5, sha1, sha256, conanfile, **kwargs):
        sources_cache = False
        h = None
        if conanfile is not None:
            if sha256:
                h = sha256
                sources_cache = True
            else:
                ConanOutput()\
                    .warning("Expected sha256 to be used as file checksums for downloaded sources")
        if h is None:
            h = self._get_hash(url, md5, sha1, sha256)

        with self._lock(h):
            if sources_cache:
                cached_path = os.path.join(self._download_cache.get_local_sources_cache_path(), h)
            else:
                cached_path = os.path.join(self._download_cache.get_local_conan_cache_path(), h)
            remove_if_dirty(cached_path)

            if not os.path.exists(cached_path):
                with set_dirty_context_manager(cached_path):
                    self._file_downloader.download(url, cached_path, md5=md5,
                                                   sha1=sha1, sha256=sha256, **kwargs)
            if sources_cache:
                summary_path = cached_path + ".json"
                if os.path.exists(summary_path):
                    summary = json.loads(load(summary_path))
                else:
                    summary = {}

                try:
                    summary_key = conanfile.ref.repr_notime()
                except AttributeError:
                    # The recipe path would be different between machines
                    # So best we can do is to set this as unknown
                    summary_key = "unknown"

                urls = summary.setdefault(summary_key, [])
                if url not in urls:
                    urls.append(url)
                save(summary_path, json.dumps(summary))
            # Everything good, file in the cache, just copy it to final destination
            file_path = os.path.abspath(file_path)
            mkdir(os.path.dirname(file_path))
            shutil.copy2(cached_path, file_path)

