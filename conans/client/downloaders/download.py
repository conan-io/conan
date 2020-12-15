from conans.client.downloaders.artifactory_cache_downloader import ArtifactoryCacheDownloader
from conans.client.downloaders.cached_file_downloader import CachedFileDownloader
from conans.client.downloaders.file_downloader import FileDownloader


def run_downloader(requester, output, verify, config, user_download=False, use_cache=True, **kwargs):
    downloader = FileDownloader(requester=requester, output=output, verify=verify, config=config)

    sources_backup = config.sources_backup
    if sources_backup:
        downloader = ArtifactoryCacheDownloader(sources_backup, downloader)

    if use_cache and config.download_cache:
        downloader = CachedFileDownloader(config.download_cache, downloader,
                                          user_download=user_download)
    return downloader.download(**kwargs)
