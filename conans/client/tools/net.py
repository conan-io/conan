import os
import copy

from conans.client.rest.download_cache import CachedFileDownloader
from conans.client.rest.uploader_downloader import FileDownloader
from conans.client.tools.files import check_md5, check_sha1, check_sha256, unzip
from conans.errors import ConanException, NotFoundException, ConanConnectionError
from conans.util.fallbacks import default_output, default_requester


def get(url, md5='', sha1='', sha256='', destination=".", filename="", keep_permissions=False,
        pattern=None, requester=None, output=None, verify=True, retry=None, retry_wait=None,
        overwrite=False, auth=None, headers=None):
    """ high level downloader + unzipper + (optional hash checker) + delete temporary zip
    """
    if not filename and ("?" in url or "=" in url):
        raise ConanException("Cannot deduce file name from url. Use 'filename' parameter.")

    filename = filename or os.path.basename(url)
    download(url, filename, out=output, requester=requester, verify=verify, retry=retry,
             retry_wait=retry_wait, overwrite=overwrite, auth=auth, headers=headers,
             md5=md5, sha1=sha1, sha256=sha256)
    unzip(filename, destination=destination, keep_permissions=keep_permissions, pattern=pattern,
          output=output)
    os.unlink(filename)


def ftp_download(ip, filename, login='', password='', output=None):
    """ Retrieves a file from an FTP server

    :param ip: The IP or address of the ftp server. It can be a list, which only the first one will
               be downloaded, and the follow URLs will be used as mirror in case of download error.
    :param filename: The filename, including the path/folder where it is located. It can be a list,
                     which only the first one will be downloaded, and the follow URLs will be used
                     as mirror in case of download error.
    :param login: Login credentials for the ftp server. It can be a list, which only the first one
                  will be downloaded, and the follow URLs will be used as mirror in case of download
                  error.
    :param password: Password credentials for the ftp server. It can be a list,
                     which only the first one will be downloaded, and the follow URLs will be used
                     as mirror in case of download error.
    :param output: An object with a write() method can be passed to get the output
    :return: None
    """
    output = default_output(output, 'conans.client.tools.net.ftp_download')
    ips = [ip] if isinstance(ip, str) else ip
    filenames = copy.copy([filename]) if isinstance(filename, str) else copy.copy(filename)
    logins = [login] if isinstance(login, str) else login
    passwords = [password] if isinstance(password, str) else password
    import ftplib
    for index, ip_it in enumerate(ips):
        try:
            ftp = ftplib.FTP(ip_it)
            ftp.login(logins[index], passwords[index])
            filepath, filename = os.path.split(filenames[index])
            if filepath:
                ftp.cwd(filepath)
            with open(filename, 'wb') as f:
                ftp.retrbinary('RETR ' + filename, f.write)
            break
        except Exception as e:
            try:
                os.unlink(filename)
            except OSError:
                pass
            if (index + 1) == len(ips):
                raise ConanException("Error in FTP download from {}\n{}".format(ip_it, str(e)))
            output.warn("Could not download the file {} from {}. Trying a new mirror."
                        .format(filename, ip_it))
        finally:
            try:
                ftp.quit()
            except Exception:
                pass


def download(url, filename, verify=True, out=None, retry=None, retry_wait=None, overwrite=False,
             auth=None, headers=None, requester=None, md5='', sha1='', sha256=''):
    """Retrieves a file from a given URL into a file with a given filename.
       It uses certificates from a list of known verifiers for https downloads,
       but this can be optionally disabled.

    :param url: URL to download. It can be a list, which only the first one will be downloaded, and
                the follow URLs will be used as mirror in case of download error.
    :param filename: Name of the file to be created in the local storage
    :param verify: When False, disables https certificate validation
    :param out: An object with a write() method can be passed to get the output. stdout will use if
                not specified
    :param retry: Number of retries in case of failure. Default is overriden by general.retry in the
                  conan.conf file or an env variable CONAN_RETRY
    :param retry_wait: Seconds to wait between download attempts. Default is overriden by
                       general.retry_wait in the conan.conf file or an env variable CONAN_RETRY_WAIT
    :param overwrite: When True, Conan will overwrite the destination file if exists. Otherwise it
                      will raise an exception
    :param auth: A tuple of user and password to use HTTPBasic authentication
    :param headers: A dictionary with additional headers
    :param requester: HTTP requests instance
    :param md5: MD5 hash code to check the downloaded file. It can be a list, where each index
                corresponds to the same index in the URL list.
    :param sha1: SHA-1 hash code to check the downloaded file It can be a list, where each index
                 corresponds to the same index in the URL list.
    :param sha256: SHA-256 hash code to check the downloaded file It can be a list, where each index
                   corresponds to the same index in the URL list.
    :return: None
    """
    out = default_output(out, 'conans.client.tools.net.download')
    requester = default_requester(requester, 'conans.client.tools.net.download')
    from conans.tools import _global_config as config

    # It might be possible that users provide their own requester
    retry = retry if retry is not None else config.retry
    retry = retry if retry is not None else 1
    retry_wait = retry_wait if retry_wait is not None else config.retry_wait
    retry_wait = retry_wait if retry_wait is not None else 5

    downloader = FileDownloader(requester=requester, output=out, verify=verify, config=config)
    url = [url] if isinstance(url, str) else url
    checksum = sha256 or sha1 or md5
    md5 = [md5] if isinstance(md5, str) else md5
    sha1 = [sha1] if isinstance(sha1, str) else sha1
    sha256 = [sha256] if isinstance(sha256, str) else sha256
    for index, url_it in enumerate(url):
        try:
            # The download cache is only used if a checksum is provided, otherwise, a normal download
            if config and config.download_cache and checksum:
                downloader = CachedFileDownloader(config.download_cache, downloader, user_download=True)
                downloader.download(url_it, filename, retry=retry, retry_wait=retry_wait,
                                    overwrite=overwrite, auth=auth, headers=headers, md5=md5[index],
                                    sha1=sha1[index], sha256=sha256[index])
            else:
                downloader.download(url_it, filename, retry=retry, retry_wait=retry_wait,
                                    overwrite=overwrite, auth=auth, headers=headers)
                if md5[index]:
                    check_md5(filename, md5[index])
                if sha1[index]:
                    check_sha1(filename, sha1[index])
                if sha256[index]:
                    check_sha256(filename, sha256[index])

            out.writeln("")
            break
        except (ConanConnectionError, NotFoundException):
            if (index + 1) == len(url):
                raise
            out.warn("Could not download from the url {}. Using the next available url."
                     .format(url_it))
