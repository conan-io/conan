import os
import traceback
import time

from tqdm import tqdm

from conans.util import progress_bar
from conans.client.rest import response_to_str
from conans.errors import AuthenticationException, ConanConnectionError, ConanException, \
    NotFoundException, ForbiddenException, RequestErrorException
from conans.util.files import mkdir, save_append, sha1sum, to_file_bytes
from conans.util.log import logger
from conans.util.tracer import log_download

TIMEOUT_BEAT_SECONDS = 30
TIMEOUT_BEAT_CHARACTER = '.'
CONTENT_CHUNK_SIZE = 10 * 1024

class FileUploader(object):

    def __init__(self, requester, output, verify, chunk_size=1000):
        self.chunk_size = chunk_size
        self.output = output
        self.requester = requester
        self.verify = verify

    def upload(self, url, abs_path, auth=None, dedup=False, retry=None, retry_wait=None,
               headers=None):
        retry = retry if retry is not None else self.requester.retry
        retry = retry if retry is not None else 1
        retry_wait = retry_wait if retry_wait is not None else self.requester.retry_wait
        retry_wait = retry_wait if retry_wait is not None else 5

        # Send always the header with the Sha1
        headers = headers or {}
        headers["X-Checksum-Sha1"] = sha1sum(abs_path)
        if dedup:
            dedup_headers = {"X-Checksum-Deploy": "true"}
            if headers:
                dedup_headers.update(headers)
            response = self.requester.put(url, data="", verify=self.verify, headers=dedup_headers,
                                          auth=auth)
            if response.status_code == 400:
                raise RequestErrorException(response_to_str(response))

            if response.status_code == 401:
                raise AuthenticationException(response_to_str(response))

            if response.status_code == 403:
                if auth.token is None:
                    raise AuthenticationException(response_to_str(response))
                raise ForbiddenException(response_to_str(response))
            if response.status_code == 201:  # Artifactory returns 201 if the file is there
                return response

        ret = call_with_retry(self.output, retry, retry_wait, self._upload_file, url,
                              abs_path=abs_path, headers=headers, auth=auth)
        return ret

    def _upload_file(self, url, abs_path,  headers, auth):
        with progress_bar.open_binary(abs_path,
                                      desc="Uploading {}".format(os.path.basename(abs_path)),
                                      output=self.output) as data:
            try:
                response = self.requester.put(url, data=data, verify=self.verify,
                                              headers=headers, auth=auth)

                if response.status_code == 400:
                    raise RequestErrorException(response_to_str(response))

                if response.status_code == 401:
                    raise AuthenticationException(response_to_str(response))

                if response.status_code == 403:
                    if auth.token is None:
                        raise AuthenticationException(response_to_str(response))
                    raise ForbiddenException(response_to_str(response))

                response.raise_for_status()  # Raise HTTPError for bad http response status

            except ConanException:
                raise
            except Exception as exc:
                raise ConanException(exc)

        return response


def _download_data(downloader):
    if downloader.finished_download:
        downloader.save()
    else:
        total_length = downloader.total_length
        encoding = downloader.encoding
        gzip = (encoding == "gzip")
        # chunked can be a problem:
        # https://www.greenbytes.de/tech/webdav/rfc2616.html#rfc.section.4.4
        # It will not send content-length or should be ignored
        dl_size = downloader.download()
        if dl_size != total_length and not gzip:
            raise ConanException("Transfer interrupted before "
                                 "complete: %s < %s" % (dl_size, total_length))
    if downloader.data is not None:
        return bytes(downloader.data)
    else:
        return None


class FileDownloader(object):

    def __init__(self, requester, output, verify, chunk_size=1000):
        self.chunk_size = chunk_size
        self.output = output
        self.requester = requester
        self.verify = verify

    def download(self, url, file_path=None, auth=None, retry=None, retry_wait=None, overwrite=False,
                 headers=None):
        retry = retry if retry is not None else self.requester.retry
        retry = retry if retry is not None else 2
        retry_wait = retry_wait if retry_wait is not None else self.requester.retry_wait
        retry_wait = retry_wait if retry_wait is not None else 0

        if file_path and not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)

        if file_path and os.path.exists(file_path):
            if overwrite:
                if self.output:
                    self.output.warn("file '%s' already exists, overwriting" % file_path)
            else:
                # Should not happen, better to raise, probably we had to remove
                # the dest folder before
                raise ConanException("Error, the file to download already exists: '%s'" % file_path)

        return call_with_retry(self.output, retry, retry_wait, self._download_file, url, auth,
                               headers, file_path)

    def _download_file(self, url, auth, headers, file_path):
        content_file = open(file_path, 'wb')
        t1 = time.time()
        try:
            response = self.requester.get(url, stream=True, verify=self.verify, auth=auth,
                                          headers=headers)
        except Exception as exc:
            raise ConanException("Error downloading file %s: '%s'" % (url, exc))

        if not response.ok:
            if response.status_code == 404:
                raise NotFoundException("Not found: %s" % url)
            elif response.status_code == 403:
                if auth.token is None:
                    raise AuthenticationException(response_to_str(response))
                raise ForbiddenException(response_to_str(response))
            elif response.status_code == 401:
                raise AuthenticationException()
            raise ConanException("Error %d downloading file %s" % (response.status_code, url))

        def read_response(chunk_size):
            try:
                # Special case for urllib3.
                for chunk in response.raw.stream(
                        chunk_size,
                        decode_content=False):
                    yield chunk
            except AttributeError:
                # Standard file-like object.
                while True:
                    chunk = response.raw.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk

        def written_chunks(chunks):
            for chunk in chunks:
                content_file.write(chunk)
                yield chunk

        try:
            logger.debug("DOWNLOAD: %s" % url)
            total_length = response.headers.get('content-length') or len(response.content)
            _progress_indicator = progress_bar.DownloadProgress(total_length, self.output,
                                                                description="Downloading {}".format(
                                                                    os.path.basename(
                                                                        self._file_path)))
            downloaded_chunks = written_chunks(
                _progress_indicator.update(
                    read_response(CONTENT_CHUNK_SIZE),
                    CONTENT_CHUNK_SIZE
                )
            )
            duration = time.time() - t1
            log_download(url, duration)
            content_file.close()
            return downloaded_chunks # o consume(downloaded_chunks)

        except Exception as e:
            logger.debug(e.__class__)
            logger.debug(traceback.format_exc())
            # If this part failed, it means problems with the connection to server
            raise ConanConnectionError("Download failed, check server, possibly try again\n%s"
                                       % str(e))


def print_progress(output, units, progress=""):
    if output.is_terminal:
        output.rewrite_line("[%s%s] %s" % ('=' * units, ' ' * (50 - units), progress))


def call_with_retry(out, retry, retry_wait, method, *args, **kwargs):
    for counter in range(retry + 1):
        try:
            return method(*args, **kwargs)
        except (NotFoundException, ForbiddenException, AuthenticationException,
                RequestErrorException):
            raise
        except ConanException as exc:
            if counter == retry:
                raise
            else:
                if out:
                    out.error(exc)
                    out.info("Waiting %d seconds to retry..." % retry_wait)
                time.sleep(retry_wait)
