from urllib.parse import urlsplit, urlunsplit

from six.moves.urllib.parse import quote

from conans.client.rest.file_uploader import FileUploader
from conans.util.sha import sha256 as sha256_sum


class ArtifactoryCacheDownloader(object):

    def __init__(self, rt_base_url, file_downloader, requester, output, verify, config,
                 user_download=False):
        self._rt_base_url = rt_base_url  # TBD: expected full url with credentials
        self._file_downloader = file_downloader
        self._user_download = user_download
        self._requester = requester
        self._file_uploader = FileUploader(requester, output, verify, config)

    def _put(self, rt_path, file_path, **props):
        """ Put the 'local_filepath' to remote and assign given properties """
        try:
            matrix_params_str = ";".join(
                ["{}={}".format(key, quote(value, safe='')) for key, value in props.items()])
            url = self._rt_base_url + ";" + matrix_params_str + "/" + rt_path
            self._file_uploader.upload(url, abs_path=file_path)
        except Exception as e:
            # TODO: Check different exceptions
            return None

    def _try_get(self, rt_path, file_path):
        """ Try to get remote file, return None if file is not found """
        try:
            url = self._rt_base_url + "/" + rt_path
            # TODO: Here we want to invoke requester, not my chained file_downloader
            self._file_downloader.download(url=url, file_path=file_path)
            return True
        except Exception:
            # TODO: Check different exceptions
            return None

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
