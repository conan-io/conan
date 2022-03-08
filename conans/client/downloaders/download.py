from conans.client.downloaders.cached_file_downloader import CachedFileDownloader
from conans.client.downloaders.file_downloader import FileDownloader


def run_downloader(requester, verify, retry, retry_wait, download_cache,
                   **kwargs):
    downloader = FileDownloader(requester=requester, verify=verify,
                                config_retry=retry, config_retry_wait=retry_wait)
    if download_cache:
        downloader = CachedFileDownloader(download_cache, downloader)
    return downloader.download(**kwargs)
