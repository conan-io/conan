import os
import shutil
from contextlib import contextmanager
from threading import Lock

from urllib.parse import urlparse
from urllib.request import url2pathname

from conan.api.output import ConanOutput
from conans.client.downloaders.file_downloader import FileDownloader
from conans.client.downloaders.download_cache import DownloadCache
from conans.errors import NotFoundException, ConanException, AuthenticationException, \
    ForbiddenException, InternalServerErrorException, ChecksumSignatureMissmatchException
from conans.util.files import mkdir, set_dirty_context_manager, remove_if_dirty
from conans.util.locks import SimpleLock


def sources_caching_download(conanfile, urls, file_path,
                             retry, retry_wait, verify_ssl, auth, headers,
                             md5, sha1, sha256):
    global_conf = conanfile._conan_helpers.global_conf
    download_cache = global_conf.get("core.sources:download_cache")
    backups_urls = global_conf.get("core.sources:download_urls", check_type=list)
    if not (backups_urls or download_cache):
        _download_from_urls(urls, file_path, retry, retry_wait, verify_ssl, auth, headers,
                            md5, sha1, sha256)
        return

    # We are going to use the download_urls definition for backups
    download_cache = download_cache or cache.default_sources_backup_folder
    # regular local shared download cache, not using Conan backup sources servers
    backups_urls = backups_urls or ["origin"]
    if download_cache and not os.path.isabs(download_cache):
        raise ConanException("core.download:download_cache must be an absolute path")
    os.makedirs(os.path.dirname(filename), exist_ok=True)  # filename in subfolder must exist


def _download_from_urls(urls, file_path, retry, retry_wait, verify_ssl, auth, headers,
                        md5, sha1, sha256):
    file_downloader = FileDownloader(requester)
    if not isinstance(urls, (list, tuple)):
        urls = [urls]
    messages = []
    for url in urls:
        try:
            if url.startswith("file:"):
                file_origin = url2pathname(urlparse(url).path)
                shutil.copyfile(file_origin, file_path)
                file_downloader.check_checksum(file_path, md5, sha1, sha256)
            else:
                file_downloader.download(url, file_path, retry=retry, retry_wait=retry_wait,
                                         verify_ssl=verify_ssl, auth=auth, overwrite=True,
                                         headers=headers, md5=md5, sha1=sha1, sha256=sha256)
            return url
        except Exception as error:
            messages.append(f"Could not download from the URL {url}: {error}.")
    # If we didn't succeed, raise error
    raise ConanException("\n".join(messages))


class CachingFileDownloader:

    def __init__(self, requester, download_cache):
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

    def _handle_sources_download(self, url, conanfile, h, cached_path, sha256, **kwargs):
        global_conf = conanfile._conan_helpers.global_conf
        origin_placeholder = "origin"
        # TODO: Make download_urls default to [origin_placeholder, "https://center-sources.conan.io/"]
        download_urls = global_conf.get("core.backup_sources:download_urls", check_type=list)
        if not download_urls:
            raise ConanException(
                f"There are no URLs defined to fetch {url} from in 'core.backup_sources:download_urls'.\n"
                f"Set the conf to ['{origin_placeholder}'] to allow downloading from the internet.")

        found = False
        for download_url in download_urls:
            try:
                if download_url == origin_placeholder:
                    self._file_downloader.download(url, cached_path, sha256=sha256, **kwargs)
                else:
                    self._file_downloader.download(download_url + h, cached_path, sha256=sha256,
                                                   **kwargs)
                    self._file_downloader.download(download_url + h + ".json", cached_path + ".json",
                                                   **kwargs)
                found = True
                location = "origin" if download_url == origin_placeholder else "remote backup"
                conanfile.output.info(f"Sources from {url} found in {location} {download_url}")
                break
            except NotFoundException:
                if download_url == origin_placeholder and download_urls.index(origin_placeholder) == 0:
                    conanfile.output.warning(
                        f"File could not be fetched from origin '{url}', trying with sources backups next")
            except (AuthenticationException, ForbiddenException) as e:
                if download_url == origin_placeholder:
                    conanfile.output.warning(f"Authorization required for origin '{url}', trying with sources backups")
                else:
                    raise ConanException(
                        f"The source backup server '{download_url}' needs authentication"
                        f"/permissions, please provide 'source_credentials.json': {e}")
            except InternalServerErrorException:
                conanfile.output.warning(f"Internal server error in {download_url} while trying to download {url}")
                # TODO: Should we really break if a backup source returns 500?
                if download_url != origin_placeholder:
                    raise
            except ChecksumSignatureMissmatchException as e:
                conanfile.output.warning(f"Signature missmatch for {url} in {download_url}, skipping: {e}")
            except ConanException:
                raise
        if not found:
            raise ConanException(f"'{url}' could not be fetched from any of {download_urls}")

    def _caching_download(self, url, file_path, md5, sha1, sha256, conanfile, **kwargs):
        cached_path, h = self._download_cache.get_cache_path(url, md5, sha1, sha256, conanfile)
        sources_download = conanfile and sha256
        with self._lock(h):
            remove_if_dirty(cached_path)

            if not os.path.exists(cached_path):
                with set_dirty_context_manager(cached_path):
                    if sources_download:
                        self._handle_sources_download(url, conanfile, h, cached_path, sha256,
                                                      **kwargs)
                    else:
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
