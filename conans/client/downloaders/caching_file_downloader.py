import json
import os
import shutil

from urllib.parse import urlparse
from urllib.request import url2pathname

from conans.client.downloaders.file_downloader import FileDownloader
from conans.client.downloaders.download_cache import DownloadCache
from conans.errors import NotFoundException, ConanException, AuthenticationException, \
    ForbiddenException
from conans.util.dates import timestamp_now
from conans.util.files import mkdir, set_dirty_context_manager, remove_if_dirty, load, save


class SourcesCachingDownloader:
    """ Class for downloading recipe download() urls
    if the config is active, it can use caching/backup-sources
    """
    def __init__(self, conanfile):
        helpers = getattr(conanfile, "_conan_helpers")
        self._global_conf = helpers.global_conf
        self._file_downloader = FileDownloader(helpers.requester)
        self._cache = helpers.cache
        self._output = conanfile.output
        self._conanfile = conanfile

    def download(self, urls, file_path,
                 retry, retry_wait, verify_ssl, auth, headers, md5, sha1, sha256):
        download_cache_folder = self._global_conf.get("core.sources:download_cache")
        backups_urls = self._global_conf.get("core.sources:download_urls", check_type=list)
        if not (backups_urls or download_cache_folder) or not sha256:
            # regular, non backup/caching download
            if backups_urls or download_cache_folder:
                self._output.warning("Cannot cache download() without sha256 checksum")
            self._download_from_urls(urls, file_path, retry, retry_wait, verify_ssl, auth, headers,
                                     md5, sha1, sha256)
        else:
            self._caching_download(urls, file_path,
                                   retry, retry_wait, verify_ssl, auth, headers, md5, sha1, sha256,
                                   download_cache_folder, backups_urls)

    def _caching_download(self, urls, file_path,
                          retry, retry_wait, verify_ssl, auth, headers, md5, sha1, sha256,
                          download_cache_folder, backups_urls):
        # We are going to use the download_urls definition for backups
        download_cache_folder = download_cache_folder or self._cache.default_sources_backup_folder
        # regular local shared download cache, not using Conan backup sources servers
        backups_urls = backups_urls or ["origin"]
        if download_cache_folder and not os.path.isabs(download_cache_folder):
            raise ConanException("core.download:download_cache must be an absolute path")

        download_cache = DownloadCache(download_cache_folder)
        cached_path = download_cache.source_path(sha256)
        with download_cache.lock(sha256):
            remove_if_dirty(cached_path)

            if os.path.exists(cached_path):
                self._output.info(f"Source {urls} retrieved from local download cache")
            else:
                with set_dirty_context_manager(cached_path):
                    for backup_url in backups_urls:
                        is_last = backup_url is backups_urls[-1]
                        if backup_url == "origin":  # recipe defined URLs
                            if self._origin_download(urls, cached_path, retry, retry_wait,
                                                     verify_ssl, auth, headers, md5, sha1, sha256,
                                                     is_last):
                                break
                        else:
                            if self._backup_download(backup_url, backups_urls, sha256, cached_path,
                                                     urls, is_last):
                                break

            self._update_backup_sources_json(cached_path, urls)
            # Everything good, file in the cache, just copy it to final destination
            mkdir(os.path.dirname(file_path))
            shutil.copy2(cached_path, file_path)

    def _origin_download(self, urls, cached_path, retry, retry_wait,
                         verify_ssl, auth, headers, md5, sha1, sha256, is_last):
        try:
            self._download_from_urls(urls, cached_path, retry, retry_wait,
                                     verify_ssl, auth, headers, md5, sha1, sha256)
        except ConanException as e:
            if is_last:
                raise
            else:
                # TODO: Improve printing of AuthenticationException
                self._output.warning(f"Sources for {urls} failed in 'origin': {e}")
                self._output.warning("Checking backups")
        else:
            if not is_last:
                self._output.info(f"Sources for {urls} found in origin")
            return True

    def _backup_download(self, backup_url, backups_urls, sha256, cached_path, urls, is_last):
        try:
            self._file_downloader.download(backup_url + sha256, cached_path, sha256=sha256)
            self._file_downloader.download(backup_url + sha256 + ".json", cached_path + ".json")
            self._output.info(f"Sources for {urls} found in remote backup {backup_url}")
            return True
        except NotFoundException:
            if is_last:
                raise NotFoundException(f"File {urls} not found in {backups_urls}")
            else:
                self._output.warning(f"Sources not found in backup {backup_url}")
        except (AuthenticationException, ForbiddenException) as e:
            raise ConanException(f"The source backup server '{backup_url}' "
                                 f"needs authentication: {e}. "
                                 f"Please provide 'source_credentials.json'")

    def _update_backup_sources_json(self, cached_path, urls):
        summary_path = cached_path + ".json"
        if os.path.exists(summary_path):
            summary = json.loads(load(summary_path))
        else:
            summary = {"references": {}, "timestamp": timestamp_now()}

        try:
            summary_key = str(self._conanfile.ref)
        except AttributeError:
            # The recipe path would be different between machines
            # So best we can do is to set this as unknown
            summary_key = "unknown"

        if not isinstance(urls, (list, tuple)):
            urls = [urls]
        existing_urls = summary["references"].setdefault(summary_key, [])
        existing_urls.extend(url for url in urls if url not in existing_urls)
        save(summary_path, json.dumps(summary))

    def _download_from_urls(self, urls, file_path, retry, retry_wait, verify_ssl, auth, headers,
                            md5, sha1, sha256):
        os.makedirs(os.path.dirname(file_path), exist_ok=True)  # filename in subfolder must exist
        if not isinstance(urls, (list, tuple)):
            urls = [urls]
        for url in urls:
            try:
                if url.startswith("file:"):
                    file_origin = url2pathname(urlparse(url).path)
                    shutil.copyfile(file_origin, file_path)
                    self._file_downloader.check_checksum(file_path, md5, sha1, sha256)
                else:
                    self._file_downloader.download(url, file_path, retry, retry_wait, verify_ssl,
                                                   auth, True, headers, md5, sha1, sha256)
                return
            except Exception as error:
                if url != urls[-1]:
                    msg = f"Could not download from the URL {url}: {error}."
                    self._output.warning(msg)
                    self._output.info("Trying another mirror.")
                else:
                    raise


class ConanInternalCacheDownloader:
    """ This is used for the download of Conan packages from server, not for sources
    """
    def __init__(self, requester, config):
        self._download_cache = config.get("core.download:download_cache")
        if self._download_cache and not os.path.isabs(self._download_cache):
            raise ConanException("core.download:download_cache must be an absolute path")
        self._file_downloader = FileDownloader(requester)

    def download(self, url, file_path, auth, verify_ssl, retry, retry_wait):
        if not self._download_cache:
            self._file_downloader.download(url, file_path, retry=retry, retry_wait=retry_wait,
                                           verify_ssl=verify_ssl, auth=auth, overwrite=False)
            return

        download_cache = DownloadCache(self._download_cache)
        cached_path, h = download_cache.cached_path(url)
        with download_cache.lock(h):
            remove_if_dirty(cached_path)

            if not os.path.exists(cached_path):
                with set_dirty_context_manager(cached_path):
                    self._file_downloader.download(url, cached_path, retry=retry,
                                                   retry_wait=retry_wait, verify_ssl=verify_ssl,
                                                   auth=auth, overwrite=False)
            # Everything good, file in the cache, just copy it to final destination
            mkdir(os.path.dirname(file_path))
            shutil.copy2(cached_path, file_path)
