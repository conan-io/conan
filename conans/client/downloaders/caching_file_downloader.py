import os
import shutil
from contextlib import contextmanager
from threading import Lock

from conan.api.output import ConanOutput
from conans.client.downloaders.file_downloader import FileDownloader
from conans.client.downloaders.download_cache import DownloadCache
from conans.errors import NotFoundException
from conans.util.files import mkdir, set_dirty_context_manager, remove_if_dirty
from conans.util.locks import SimpleLock


class CachingFileDownloader:

    def __init__(self, requester,  download_cache):
        self._output = ConanOutput()
        self._download_cache = DownloadCache(download_cache) if download_cache else None
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

    def _try_download_from_backup(self, url, conanfile, h, cached_path, sha256, **kwargs):
        download_urls = conanfile.conf.get("tools.backup_sources:download_urls")
        if not download_urls:
            return False
        found_in_backup = False
        for download_url in download_urls:
            try:
                self._file_downloader.download(download_url + h, cached_path,
                                               sha256=sha256, **kwargs)
                self._file_downloader.download(download_url + h + ".json",
                                               cached_path + ".json", **kwargs)
                found_in_backup = True
                conanfile.output.info(f"Sources from {url} found in remote backup {download_url}")
                break
            except NotFoundException:
                # TODO: What happens if sha256 missmatch?
                pass
        if not found_in_backup:
            # TODO: Policy to control this behaviour
            pass
        return found_in_backup

    def _caching_download(self, url, file_path, md5, sha1, sha256, conanfile, **kwargs):
        cached_path, h = self._download_cache.get_cache_path(url, md5, sha1, sha256, conanfile)
        sources_download = conanfile and sha256
        with self._lock(h):
            remove_if_dirty(cached_path)

            if not os.path.exists(cached_path):
                with set_dirty_context_manager(cached_path):
                    found_in_backup = False
                    if sources_download:
                        found_in_backup = self._try_download_from_backup(url, conanfile, h,
                                                                         cached_path, sha256,
                                                                         **kwargs)
                    if not found_in_backup:
                        self._file_downloader.download(url, cached_path, md5=md5,
                                                       sha1=sha1, sha256=sha256, **kwargs)
            elif sources_download:
                conanfile.output.info(f"Source {url} retrieved from local download cache")

            if sources_download:
                self._download_cache.update_backup_sources_json(cached_path, conanfile, url)

            # Everything good, file in the cache, just copy it to final destination
            file_path = os.path.abspath(file_path)
            mkdir(os.path.dirname(file_path))
            shutil.copy2(cached_path, file_path)
