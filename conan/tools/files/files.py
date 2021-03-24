import errno
import os

from conans.errors import ConanException
from conans.util.files import decode_text, to_file_bytes
from conans.client.tools.files import unzip
from conans.client.downloaders.download import run_downloader


def load(conanfile, path, binary=False, encoding="auto"):
    """ Loads a file content """
    with open(path, 'rb') as handle:
        tmp = handle.read()
        # TODO: Get rid of encoding auto-detection
        return tmp if binary else decode_text(tmp, encoding)


def save(conanfile, path, content, append=False):
    if append:
        mode = "ab"
        try:
            os.makedirs(os.path.dirname(path))
        except Exception:
            pass
    else:
        mode = "wb"
        dir_path = os.path.dirname(path)
        if not os.path.isdir(dir_path):
            try:
                os.makedirs(dir_path)
            except OSError as error:
                if error.errno not in (errno.EEXIST, errno.ENOENT):
                    raise OSError("The folder {} does not exist and could not be created ({})."
                                  .format(dir_path, error.strerror))
            except Exception:
                raise

    with open(path, mode) as handle:
        handle.write(to_file_bytes(content, encoding="utf-8"))


def mkdir(conanfile, path):
    """Recursive mkdir, doesnt fail if already existing"""
    if os.path.exists(path):
        return
    os.makedirs(path)


def get(conanfile, url, md5='', sha1='', sha256='', destination=".", filename="", keep_permissions=False,
        pattern=None, verify=True, retry=None, retry_wait=None,
        overwrite=False, auth=None, headers=None, strip_root=False):
    """ high level downloader + unzipper + (optional hash checker) + delete temporary zip
    """
    requester = conanfile._conan_requester
    output = conanfile.output
    if not filename:  # deduce filename from the URL
        url_base = url[0] if isinstance(url, (list, tuple)) else url
        if "?" in url_base or "=" in url_base:
            raise ConanException("Cannot deduce file name from the url: '{}'. Use 'filename' "
                                 "parameter.".format(url_base))
        filename = os.path.basename(url_base)

    download(url, filename, out=output, requester=requester, verify=verify,
             retry=retry, retry_wait=retry_wait, overwrite=overwrite, auth=auth, headers=headers,
             md5=md5, sha1=sha1, sha256=sha256)
    unzip(filename, destination=destination, keep_permissions=keep_permissions, pattern=pattern,
          output=output, strip_root=strip_root)
    os.unlink(filename)


def ftp_download(conanfile, ip, filename, login='', password=''):
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


def download(conanfile, url, filename, verify=True, out=None, retry=None, retry_wait=None, overwrite=False,
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
    :param md5: MD5 hash code to check the downloaded file
    :param sha1: SHA-1 hash code to check the downloaded file
    :param sha256: SHA-256 hash code to check the downloaded file
    :return: None
    """
    # TODO: Add all parameters to the new conf
    out = conanfile.output
    requester = conanfile._conan_requester
    config = conanfile.conf

    # It might be possible that users provide their own requester
    retry = retry if retry is not None else int(config["tools.files.download"].retry)
    retry = retry if retry is not None else 1
    retry_wait = retry_wait if retry_wait is not None else int(config["tools.files.download"].retry_wait)
    retry_wait = retry_wait if retry_wait is not None else 5

    checksum = sha256 or sha1 or md5

    def _download_file(file_url):
        # The download cache is only used if a checksum is provided, otherwise, a normal download
        run_downloader(requester=requester, output=out, verify=verify, config=config,
                       user_download=True, use_cache=bool(config and checksum), url=file_url,
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
