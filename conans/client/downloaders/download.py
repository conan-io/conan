from conans.client.downloaders.cached_file_downloader import CachedFileDownloader
from conans.client.downloaders.file_downloader import FileDownloader
from conans.client.downloaders.local_file_downloader import LocalFileDownloader


def run_downloader(requester, output, verify, retry, retry_wait, download_cache, local_filesystem,
                   user_download=False, **kwargs):
    downloader = FileDownloader(requester=requester, output=output, verify=verify,
                                config_retry=retry, config_retry_wait=retry_wait)
    if local_filesystem:
        downloader = LocalFileDownloader(output=output)
    elif download_cache:
        downloader = CachedFileDownloader(download_cache, downloader, user_download=user_download)
    return downloader.download(**kwargs)
