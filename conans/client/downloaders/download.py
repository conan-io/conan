from .cached_file_downloader import CachedFileDownloader
from .file_downloader import FileDownloader


def run_downloader(requester, output, verify, config, user_download=False, **kwargs):
    downloader = FileDownloader(requester=requester, output=output, verify=verify, config=config)
    if config.download_cache:
        downloader = CachedFileDownloader(config.download_cache, downloader,
                                          user_download=user_download)
    else:
        # TODO: Make the 'download' signature compatible
        kwargs.pop('md5')
        kwargs.pop('sha1')
        kwargs.pop('sha256')
    return downloader.download(**kwargs)
