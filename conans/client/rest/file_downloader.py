import os
import re
import time
import traceback

import six

from conans.client.rest import response_to_str
from conans.errors import AuthenticationException, ConanConnectionError, ConanException, \
    NotFoundException, ForbiddenException, RequestErrorException
from conans.util import progress_bar
from conans.util.files import mkdir
from conans.util.log import logger
from conans.util.tracer import log_download


class FileDownloader(object):

    def __init__(self, requester, output, verify, config):
        self._output = output
        self._requester = requester
        self._verify_ssl = verify
        self._config = config

    def download(self, url, file_path=None, auth=None, retry=None, retry_wait=None, overwrite=False,
                 headers=None):
        retry = retry if retry is not None else self._config.retry
        retry = retry if retry is not None else 2
        retry_wait = retry_wait if retry_wait is not None else self._config.retry_wait
        retry_wait = retry_wait if retry_wait is not None else 0

        if file_path and not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)

        if file_path and os.path.exists(file_path):
            if overwrite:
                if self._output:
                    self._output.warn("file '%s' already exists, overwriting" % file_path)
            else:
                # Should not happen, better to raise, probably we had to remove
                # the dest folder before
                raise ConanException("Error, the file to download already exists: '%s'" % file_path)

        return _call_with_retry(self._output, retry, retry_wait, self._download_file, url, auth,
                                headers, file_path)

    def _download_file(self, url, auth, headers, file_path, try_resume=False):
        t1 = time.time()
        if try_resume and file_path and os.path.exists(file_path):
            range_start = os.path.getsize(file_path)
            headers = headers.copy() if headers else {}
            headers["range"] = "bytes={}-".format(range_start)
        else:
            range_start = 0

        try:
            response = self._requester.get(url, stream=True, verify=self._verify_ssl, auth=auth,
                                           headers=headers)
        except Exception as exc:
            raise ConanException("Error downloading file %s: '%s'" % (url, exc))

        if not response.ok:
            if response.status_code == 404:
                raise NotFoundException("Not found: %s" % url)
            elif response.status_code == 403:
                if auth is None or (hasattr(auth, "token") and auth.token is None):
                    # TODO: This is a bit weird, why this conversion? Need to investigate
                    raise AuthenticationException(response_to_str(response))
                raise ForbiddenException(response_to_str(response))
            elif response.status_code == 401:
                raise AuthenticationException()
            raise ConanException("Error %d downloading file %s" % (response.status_code, url))

        def read_response(size):
            for chunk in response.iter_content(size):
                yield chunk

        def write_chunks(chunks, path):
            ret = None
            downloaded_size = range_start
            if path:
                mkdir(os.path.dirname(path))
                mode = "ab" if range_start else "wb"
                with open(path, mode) as file_handler:
                    for chunk in chunks:
                        assert ((six.PY3 and isinstance(chunk, bytes)) or
                                (six.PY2 and isinstance(chunk, str)))
                        file_handler.write(chunk)
                        downloaded_size += len(chunk)
            else:
                ret_data = bytearray()
                for chunk in chunks:
                    ret_data.extend(chunk)
                    downloaded_size += len(chunk)
                ret = bytes(ret_data)
            return ret, downloaded_size

        def get_total_length():
            if range_start:
                content_range = response.headers.get("Content-Range", "")
                match = re.match(r"^bytes (\d+)-(\d+)/(\d+)", content_range)
                if not match or range_start != int(match.group(1)):
                    raise ConanException("Error in resumed download from %s\n"
                                         "Incorrect Content-Range header %s" % (url, content_range))
                return int(match.group(3))
            else:
                total_size = response.headers.get('Content-Length') or len(response.content)
                return int(total_size)

        try:
            logger.debug("DOWNLOAD: %s" % url)
            total_length = get_total_length()
            action = "Downloading" if range_start == 0 else "Continuing download of"
            description = "{} {}".format(action, os.path.basename(file_path)) if file_path else None
            progress = progress_bar.Progress(total_length, self._output, description)
            progress.initial_value(range_start)

            chunk_size = 1024 if not file_path else 1024 * 100
            written_chunks, total_downloaded_size = write_chunks(
                progress.update(read_response(chunk_size)),
                file_path
            )
            gzip = (response.headers.get("content-encoding") == "gzip")
            response.close()
            # it seems that if gzip we don't know the size, cannot resume and shouldn't raise
            if total_downloaded_size != total_length and not gzip:
                if (file_path and total_length > total_downloaded_size > range_start
                        and response.headers.get("Accept-Ranges") == "bytes"):
                    written_chunks = self._download_file(url, auth, headers, file_path,
                                                         try_resume=True)
                else:
                    raise ConanException("Transfer interrupted before complete: %s < %s"
                                         % (total_downloaded_size, total_length))

            duration = time.time() - t1
            log_download(url, duration)
            return written_chunks

        except Exception as e:
            logger.debug(e.__class__)
            logger.debug(traceback.format_exc())
            # If this part failed, it means problems with the connection to server
            raise ConanConnectionError("Download failed, check server, possibly try again\n%s"
                                       % str(e))


def _call_with_retry(out, retry, retry_wait, method, *args, **kwargs):
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
