import os

from conans.client.downloaders.download import run_downloader
from conans.client.tools.files import check_md5, check_sha1, check_sha256, unzip
from conans.errors import ConanException
from conans.util.fallbacks import default_output, default_requester


def get(url, md5=None, sha1=None, sha256=None, destination=".", filename="", keep_permissions=False,
        pattern=None, requester=None, output=None, verify=True, retry=None, retry_wait=None,
        overwrite=False, auth=None, headers=None, strip_root=False):
    """ high level downloader + unzipper + (optional hash checker) + delete temporary zip
    """

    if not filename:  # deduce filename from the URL
        url_base = url[0] if isinstance(url, (list, tuple)) else url
        if "?" in url_base or "=" in url_base:
            raise ConanException("Cannot deduce file name from the url: '{}'. Use 'filename' "
                                 "parameter.".format(url_base))
        filename = os.path.basename(url_base)

    download(url, filename, out=output, requester=requester, verify=verify, retry=retry,
             retry_wait=retry_wait, overwrite=overwrite, auth=auth, headers=headers,
             md5=md5, sha1=sha1, sha256=sha256)
    unzip(filename, destination=destination, keep_permissions=keep_permissions, pattern=pattern,
          output=output, strip_root=strip_root)
    os.unlink(filename)


def ftp_download(ip, filename, login='', password=''):
    import ftplib
    try:
        ftp = ftplib.FTP(ip)
        ftp.login(login, password)
        filepath, filename = os.path.split(filename)
        if filepath:
            ftp.cwd(filepath)
        with open(filename, 'wb') as f:
            ftp.retrbinary('RETR ' + filename, f.write)
    except Exception as e:
        try:
            os.unlink(filename)
        except OSError:
            pass
        raise ConanException("Error in FTP download from %s\n%s" % (ip, str(e)))
    finally:
        try:
            ftp.quit()
        except Exception:
            pass


def download(url, filename, verify=True, out=None, retry=None, retry_wait=None, overwrite=False,
             auth=None, headers=None, requester=None, md5=None, sha1=None, sha256=None):
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
    :param md5: MD5 hash code to check the downloaded file
    :param sha1: SHA-1 hash code to check the downloaded file
    :param sha256: SHA-256 hash code to check the downloaded file
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

    checksum = sha256 or sha1 or md5
    download_cache = config.download_cache if checksum else None

    def _download_file(file_url):
        # The download cache is only used if a checksum is provided, otherwise, a normal download
        run_downloader(requester=requester, output=out, verify=verify,
                       user_download=True, download_cache=download_cache, url=file_url,
                       file_path=filename, retry=retry, retry_wait=retry_wait, overwrite=overwrite,
                       auth=auth, headers=headers, md5=md5, sha1=sha1, sha256=sha256)
        out.writeln("")

    if not isinstance(url, (list, tuple)):
        _download_file(url)
    else:  # We were provided several URLs to try
        for url_it in url:
            try:
                _download_file(url_it)
                break
            except Exception as error:
                message = "Could not download from the URL {}: {}.".format(url_it, str(error))
                out.warn(message + " Trying another mirror.")
        else:
            raise ConanException("All downloads from ({}) URLs have failed.".format(len(url)))
