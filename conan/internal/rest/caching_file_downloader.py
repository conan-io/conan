import os
import shutil

from urllib.parse import urlparse
from urllib.request import url2pathname

from conan.api.output import ConanOutput
from conan.internal.cache.home_paths import HomePaths
from conan.internal.rest.file_downloader import FileDownloader
from conan.internal.rest.download_cache import DownloadCache
from conan.internal.errors import AuthenticationException, ForbiddenException, NotFoundException
from conan.errors import ConanException
from conan.internal.util.files import mkdir, set_dirty_context_manager, remove_if_dirty, human_size


class SourcesCachingDownloader:
    """ Class for downloading recipe download() urls
    if the config is active, it can use caching/backup-sources
    """
    def __init__(self, conanfile):
        helpers = getattr(conanfile, "_conan_helpers")
        self._global_conf = helpers.global_conf
        self._file_downloader = FileDownloader(helpers.requester, scope=conanfile.display_name,
                                               source_credentials=True)
        self._home_folder = helpers.home_folder
        self._output = conanfile.output
        self._conanfile = conanfile

    def download(self, urls, file_path,
                 retry, retry_wait, verify_ssl, auth, headers, md5, sha1, sha256):
        download_cache_folder = self._global_conf.get("core.sources:download_cache")
        source_origins = self._global_conf.get("core.sources:download_urls", check_type=list)
        if source_origins and not download_cache_folder:
            download_cache_folder = HomePaths(self._home_folder).default_sources_backup_folder
        if download_cache_folder and not os.path.isabs(download_cache_folder):
            raise ConanException("core.sources:download_cache must be an absolute path")
        if download_cache_folder and not sha256:
            self._output.warning("Cannot cache download() without sha256 checksum")
            download_cache_folder = None  # Cannot cache
        source_origins = source_origins or ["origin"]
        if None in source_origins:
            raise ConanException(f"Incorrect 'core.sources:download_urls' contains invalid 'None'"
                                 f"url: {source_origins}")

        # First, see if it is already in the download cache
        if download_cache_folder:
            download_cache = DownloadCache(download_cache_folder)
            download_path = download_cache.source_path(sha256)
            with download_cache.lock(sha256):
                if os.path.exists(download_path):
                    self._output.info(f"Source {urls} retrieved from local download cache")
                    download_cache.update_backup_sources_json(download_path, self._conanfile, urls)
                    mkdir(os.path.dirname(file_path))
                    shutil.copy2(download_path, file_path)
                    return

        # If it is not in the download cache, we need to download it, lets try
        for backup_url in source_origins:
            if backup_url == "origin":  # download from the internet
                try:
                    self._download_from_urls(urls, file_path, retry, retry_wait, verify_ssl, auth,
                                             headers, md5, sha1, sha256)
                    break
                except Exception as e:
                    if backup_url is source_origins[-1]:
                        raise
                    self._output.warning(f"Sources for {urls} failed in 'origin': {e}")
            else:  # Download from a backup server
                try:
                    self._output.info(f"Checking backup: {backup_url}")
                    backup_url = backup_url if backup_url.endswith("/") else backup_url + "/"
                    # The download happens to the user download folder, not to the download cache
                    self._file_downloader.download(backup_url + sha256, file_path, sha256=sha256,
                                                   overwrite=True)
                    self._file_downloader.download(backup_url + sha256 + ".json",
                                                   file_path + ".json", overwrite=True)
                    self._output.info(f"Sources for {urls} found in remote backup {backup_url}")
                    break
                except NotFoundException:
                    msg = f"Sources for {urls} not found in remote backup {backup_url}"
                    if backup_url is source_origins[-1]:
                        raise NotFoundException(msg)
                    else:
                        self._output.warning(msg)
                except (AuthenticationException, ForbiddenException) as e:
                    raise ConanException(f"Authentication to source backup server '{backup_url}' "
                                         f"failed: {e}. "
                                         f"Please check your 'source_credentials.json'")

        # We might need to put it in the download cache
        if download_cache_folder:
            download_cache = DownloadCache(download_cache_folder)
            cached_path = download_cache.source_path(sha256)
            with download_cache.lock(sha256):
                os.makedirs(os.path.dirname(cached_path), exist_ok=True)
                shutil.copy(file_path, cached_path)
                if os.path.exists(file_path + ".json"):
                    shutil.move(file_path + ".json", download_cache_folder)
                download_cache.update_backup_sources_json(cached_path, self._conanfile, urls)

    def _download_from_urls(self, urls, file_path, retry, retry_wait, verify_ssl, auth, headers,
                            md5, sha1, sha256):
        """ iterate the recipe provided list of urls (mirrors, all with same checksum) until
        one succeed
        """
        os.makedirs(os.path.dirname(file_path), exist_ok=True)  # filename in subfolder must exist
        if not isinstance(urls, (list, tuple)):
            urls = [urls]
        for url in urls:
            try:
                if url.startswith("file:"):  # plain copy from local disk, no real download
                    file_origin = url2pathname(urlparse(url).path)
                    shutil.copyfile(file_origin, file_path)
                    self._file_downloader.check_checksum(file_path, md5, sha1, sha256)
                else:
                    self._file_downloader.download(url, file_path, retry, retry_wait, verify_ssl,
                                                   auth, True, headers, md5, sha1, sha256)
                self._output.info(f"Sources correctly downloaded from {url}")
                return  # Success! Return to caller
            except Exception as error:
                if url != urls[-1]:  # If it is not the last one, do not raise, warn and move to next
                    msg = f"Could not download from the URL {url}: {error}."
                    self._output.warning(msg)
                    self._output.info("Trying another mirror.")
                else:
                    raise


class ConanInternalCacheDownloader:
    """ This is used for the download of Conan packages from server, not for sources/backup sources
    """
    def __init__(self, requester, config, scope=None):
        self._download_cache = config.get("core.download:download_cache")
        if self._download_cache and not os.path.isabs(self._download_cache):
            raise ConanException("core.download:download_cache must be an absolute path")
        self._file_downloader = FileDownloader(requester, scope=scope)
        self._scope = scope

    def download(self, url, file_path, auth, verify_ssl, retry, retry_wait, metadata=False):
        if not self._download_cache or metadata:  # Metadata not cached and can be overwritten
            self._file_downloader.download(url, file_path, retry=retry, retry_wait=retry_wait,
                                           verify_ssl=verify_ssl, auth=auth, overwrite=metadata)
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
            else:  # Found in cache!
                total_length = os.path.getsize(cached_path)
                is_large_file = total_length > 10000000  # 10 MB
                if is_large_file:
                    base_name = os.path.basename(file_path)
                    hs = human_size(total_length)
                    ConanOutput(scope=self._scope).info(f"Copying {hs} {base_name} from download "
                                                        f"cache, instead of downloading it")

            # Everything good, file in the cache, just copy it to final destination
            mkdir(os.path.dirname(file_path))
            shutil.copy2(cached_path, file_path)
