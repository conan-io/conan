from conans.client.downloaders.cached_file_downloader import CachedFileDownloader
from conans.client.downloaders.file_downloader import FileDownloader


def run_downloader(requester, output, verify, retry, retry_wait, download_cache, user_download=False,
                   **kwargs):
    downloader = FileDownloader(requester=requester, output=output, verify=verify,
                                config_retry=retry, config_retry_wait=retry_wait)
    if download_cache:
        downloader = CachedFileDownloader(download_cache, downloader, user_download=user_download)
    return downloader.download(**kwargs)
