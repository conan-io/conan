from urllib.parse import urlsplit, urlunsplit
from conans.util.sha import sha256 as sha256_sum


class ArtifactoryCacheDownloader(object):

    def __init__(self, rt_base_url, file_downloader, requester, user_download=False):
        self._rt_base_url = rt_base_url  # TBD: expected full url with credentials
        self._file_downloader = file_downloader
        self._user_download = user_download
        self._requester = requester

    def _put(self, rt_path, file_path, **props):
        """ Put the 'local_filepath' to remote and assign given properties """
        pass

    def _try_get(self, rt_path, file_path):
        """ Try to get remote file, return None if file is not found """
        try:
            url = self._rt_base_url + "/" + rt_path
            response = self._requester.get(url, stream=True, verify=False)

        except Exception as exc:


    def _rt_path(self, url, checksum=None):
        # TODO: Chain classes, use same implementation as 'file_downloader'
        urltokens = urlsplit(url)
        # append empty query and fragment before unsplit
        if not self._user_download:  # removes ?signature=xxx
            url = urlunsplit(urltokens[0:3] + ("", ""))
        if checksum is not None:
            url += checksum
        h = sha256_sum(url.encode())
        return h

    def download(self, url, file_path, md5=None, sha1=None, sha256=None, *args, **kwargs):
        """ Intercept download call """
        # TODO: We don't want to intercept every call, like 'conan_sources.tgz' or
        #  'conan_package.tgz', they are already under our control. Argument from outside or
        #  something to check names here?
        checksum = sha256 or sha1 or md5
        rt_path = self._rt_path(url, checksum)
        if not self._try_get(rt_path, file_path=file_path):
            self._file_downloader.download(url=url, file_path=file_path, *args, **kwargs)
            self._put(rt_path, file_path=file_path, url=url)
