import os
import re
import time


from conan.api.output import ConanOutput
from conans.client.rest import response_to_str
from conans.errors import ConanException, NotFoundException, AuthenticationException, \
    ForbiddenException, ConanConnectionError, RequestErrorException
from conans.util.files import mkdir
from conans.util.sha import check_with_algorithm_sum
from conans.util.tracer import log_download


class FileDownloader:

    def __init__(self, requester):
        self._output = ConanOutput()
        self._requester = requester

    def download(self, url, file_path, retry=2, retry_wait=0, verify_ssl=True, auth=None,
                 overwrite=False, headers=None, md5=None, sha1=None, sha256=None):

        if not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)

        if os.path.exists(file_path):
            if overwrite:
                self._output.warning("file '%s' already exists, overwriting" % file_path)
            else:
                # Should not happen, better to raise, probably we had to remove
                # the dest folder before
                raise ConanException("Error, the file to download already exists: '%s'" % file_path)

        try:
            for counter in range(retry + 1):
                try:
                    self._download_file(url, auth, headers, file_path, verify_ssl)
                    break
                except (NotFoundException, ForbiddenException, AuthenticationException,
                        RequestErrorException):
                    raise
                except ConanException as exc:
                    if counter == retry:
                        raise
                    else:
                        self._output.error(exc)
                        self._output.info(f"Waiting {retry_wait} seconds to retry...")
                        time.sleep(retry_wait)

            self._check_checksum(file_path, md5, sha1, sha256)
        except Exception:
            if os.path.exists(file_path):
                os.remove(file_path)
            raise

    @staticmethod
    def _check_checksum(file_path, md5, sha1, sha256):
        if md5 is not None:
            check_with_algorithm_sum("md5", file_path, md5)
        if sha1 is not None:
            check_with_algorithm_sum("sha1", file_path, sha1)
        if sha256 is not None:
            check_with_algorithm_sum("sha256", file_path, sha256)

    def _download_file(self, url, auth, headers, file_path, verify_ssl, try_resume=False):
        t1 = time.time()
        if try_resume and file_path and os.path.exists(file_path):
            range_start = os.path.getsize(file_path)
            headers = headers.copy() if headers else {}
            headers["range"] = "bytes={}-".format(range_start)
        else:
            range_start = 0

        try:
            response = self._requester.get(url, stream=True, verify=verify_ssl, auth=auth,
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

        def read_response(chunk_size, path=None):
            ret = None
            downloaded_size = range_start
            if path:
                mkdir(os.path.dirname(path))
                mode = "ab" if range_start else "wb"
                with open(path, mode) as file_handler:
                    for chunk in response.iter_content(chunk_size):
                        file_handler.write(chunk)
                        downloaded_size += len(chunk)
            else:
                ret_data = bytearray()
                for chunk in response.iter_content(chunk_size):
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
            total_length = get_total_length()
            action = "Downloading" if range_start == 0 else "Continuing download of"
            description = "{} {}".format(action, os.path.basename(file_path)) if file_path else None
            if description:
                self._output.info(description)

            chunksize = 1024 if not file_path else 1024 * 100
            written_chunks, total_downloaded_size = read_response(chunksize, file_path)
            gzip = (response.headers.get("content-encoding") == "gzip")
            response.close()
            # it seems that if gzip we don't know the size, cannot resume and shouldn't raise
            if total_downloaded_size != total_length and not gzip:
                if (file_path and total_length > total_downloaded_size > range_start
                        and response.headers.get("Accept-Ranges") == "bytes"):
                    written_chunks = self._download_file(url, auth, headers, file_path, verify_ssl,
                                                         try_resume=True)
                else:
                    raise ConanException("Transfer interrupted before complete: %s < %s"
                                         % (total_downloaded_size, total_length))

            duration = time.time() - t1
            log_download(url, duration)
            return written_chunks

        except Exception as e:
            # If this part failed, it means problems with the connection to server
            raise ConanConnectionError("Download failed, check server, possibly try again\n%s"
                                       % str(e))
