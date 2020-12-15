from .utils import hash_url


class ArtifactoryCacheDownloader(object):

    def __init__(self, rt_base_url, downloader, user_download=False):
        self._rt_base_url = rt_base_url
        self._downloader = downloader
        self._user_download = user_download

    def _try_get(self, rt_path, file_path, **kwargs):
        """ Try to get remote file, return None if file is not found """
        try:
            url = self._rt_base_url + "/" + rt_path
            # TODO: Here we need to silence the output from chained downloader
            return self._downloader.download(url=url, file_path=file_path, **kwargs)
        except Exception:
            # TODO: Check different exceptions: if the checksum fails we should warn the user so
            #   they can remove the file from the Artifactory server.
            return None

    def download(self, url, file_path=None, md5=None, sha1=None, sha256=None, **kwargs):
        """ Intercept download call """
        checksum = sha256 or sha1 or md5
        h = hash_url(url, checksum, self._user_download)
        r = self._try_get(h, file_path=file_path, md5=md5, sha256=sha256, **kwargs)
        if r is None:
            r = self._downloader.download(url=url, file_path=file_path, md5=md5, sha256=sha256,
                                          **kwargs)
        return r
