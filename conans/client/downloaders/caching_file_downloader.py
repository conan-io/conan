import json
import os
import shutil

from urllib.parse import urlparse
from urllib.request import url2pathname

from conan.api.output import ConanOutput
from conans.util.sha import sha256 as compute_sha256
from conans.client.downloaders.file_downloader import FileDownloader
from conans.client.downloaders.download_cache import DownloadCache
from conans.errors import NotFoundException, ConanException
from conans.util.dates import timestamp_now
from conans.util.files import mkdir, set_dirty_context_manager, remove_if_dirty, load, save


def sources_caching_download(conanfile, urls, file_path,
                             retry, retry_wait, verify_ssl, auth, headers,
                             md5, sha1, sha256):
    helpers = getattr(conanfile, "_conan_helpers")
    global_conf = helpers.global_conf
    file_downloader = FileDownloader(helpers.requester)
    cache = helpers.cache

    download_cache = global_conf.get("core.sources:download_cache")
    backups_urls = global_conf.get("core.sources:download_urls", check_type=list)
    if not (backups_urls or download_cache) or not sha256:
        # regular, non backup/caching download
        if backups_urls or download_cache:
            conanfile.output.warning("Cannot cache download() without sha256 checksum")
        _download_from_urls(urls, file_path, retry, retry_wait, verify_ssl, auth, headers,
                            md5, sha1, sha256, file_downloader)
        return

    # We are going to use the download_urls definition for backups
    download_cache = download_cache or cache.default_sources_backup_folder
    # regular local shared download cache, not using Conan backup sources servers
    backups_urls = backups_urls or ["origin"]
    if download_cache and not os.path.isabs(download_cache):
        raise ConanException("core.download:download_cache must be an absolute path")

    cached_path = os.path.join(download_cache, "s", sha256)
    download_cache = DownloadCache(download_cache)
    with download_cache.lock(sha256):
        remove_if_dirty(cached_path)

        if os.path.exists(cached_path):
            conanfile.output.info(f"Source {urls} retrieved from local download cache")
        else:
            with set_dirty_context_manager(cached_path):
                for backup_url in backups_urls:
                    if backup_url == "origin":  # recipe defined URLs
                        try:
                            url = _download_from_urls(urls, cached_path, retry, retry_wait, verify_ssl,
                                                      auth, headers, md5, sha1, sha256, file_downloader)
                        except ConanException as e:
                            conanfile.output.warning(str(e))
                        else:
                            _update_backup_sources_json(cached_path, conanfile, url)
                            break
                    else:
                        try:
                            file_downloader.download(backup_url + sha256, cached_path, sha256=sha256)
                            file_downloader.download(backup_url + sha256 + ".json", cached_path + ".json")
                            conanfile.output.info(f"Sources for {urls} found in {backup_url}")
                            break
                        except NotFoundException:
                            pass
                else:
                    raise ConanException(f"{urls} not found in {backups_urls}")

        # Everything good, file in the cache, just copy it to final destination
        mkdir(os.path.dirname(file_path))
        shutil.copy2(cached_path, file_path)


def _update_backup_sources_json(cached_path, conanfile, url):
    summary_path = cached_path + ".json"
    if os.path.exists(summary_path):
        summary = json.loads(load(summary_path))
    else:
        summary = {"references": {}, "timestamp": timestamp_now()}

    try:
        summary_key = str(conanfile.ref)
    except AttributeError:
        # The recipe path would be different between machines
        # So best we can do is to set this as unknown
        summary_key = "unknown"

    urls = summary["references"].setdefault(summary_key, [])
    if url not in urls:
        urls.append(url)
    save(summary_path, json.dumps(summary))


def _download_from_urls(urls, file_path, retry, retry_wait, verify_ssl, auth, headers,
                        md5, sha1, sha256, file_downloader):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)  # filename in subfolder must exist
    if not isinstance(urls, (list, tuple)):
        urls = [urls]
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
            if url != urls[-1]:
                msg = f"Could not download from the URL {url}: {error}."
                ConanOutput().warning(msg)
                ConanOutput().info("Trying another mirror.")
            else:
                error.args += (f"Could not download from the URL {url}",)
                raise error


class ConanInternalCacheDownloader:
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

        h = compute_sha256(url.encode())
        cached_path = os.path.join(self._download_cache, "c", h)
        download_cache = DownloadCache(self._download_cache)
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
