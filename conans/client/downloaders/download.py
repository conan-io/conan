from conans.client.downloaders.file_downloader import FileDownloader


def run_downloader(requester, verify, retry, retry_wait, download_cache, **kwargs):
    # Legacy CachedFileDownloader does not exist anymore. Keeping run_downloader as it is just for
    # backwards compatibility
    downloader = FileDownloader(requester=requester, verify=verify,
                                config_retry=retry, config_retry_wait=retry_wait)
    return downloader.download(**kwargs)
