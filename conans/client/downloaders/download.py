from conans.client.downloaders.file_downloader import FileDownloader


def run_downloader(requester, verify, retry, retry_wait, download_cache, **kwargs):
    # Legacy CachedFileDownloader does not exist anymore. Keeping run_downloader as it is just for
    # backwards compatibility
    assert download_cache is not True, "'download_cache' parameter must be False. " \
                                       "Legacy CachedFileDownloader class does not exist anymore"
    downloader = FileDownloader(requester=requester, verify=verify,
                                config_retry=retry, config_retry_wait=retry_wait)
    return downloader.download(**kwargs)
