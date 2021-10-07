import configparser
import errno
import os
import platform
import subprocess
from contextlib import contextmanager

from conan.tools import CONAN_TOOLCHAIN_ARGS_FILE, CONAN_TOOLCHAIN_ARGS_SECTION
from conans.client.downloaders.download import run_downloader
from conans.client.tools.files import unzip, which
from conans.errors import ConanException
from conans.util.files import decode_text, to_file_bytes


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


def get(conanfile, url, md5='', sha1='', sha256='', destination=".", filename="",
        keep_permissions=False, pattern=None, verify=True, retry=None, retry_wait=None,
        auth=None, headers=None, strip_root=False):
    """ high level downloader + unzipper + (optional hash checker) + delete temporary zip
    """

    output = conanfile.output
    if not filename:  # deduce filename from the URL
        url_base = url[0] if isinstance(url, (list, tuple)) else url
        if "?" in url_base or "=" in url_base:
            raise ConanException("Cannot deduce file name from the url: '{}'. Use 'filename' "
                                 "parameter.".format(url_base))
        filename = os.path.basename(url_base)

    download(conanfile, url, filename, verify=verify,
             retry=retry, retry_wait=retry_wait, auth=auth, headers=headers,
             md5=md5, sha1=sha1, sha256=sha256)
    unzip(filename, destination=destination, keep_permissions=keep_permissions, pattern=pattern,
          output=output, strip_root=strip_root)
    os.unlink(filename)


def ftp_download(conanfile, ip, filename, login='', password=''):
    # TODO: Check if we want to join this method with download() one, based on ftp:// protocol
    # this has been requested by some users, but the signature is a bit divergent
    import ftplib
    ftp = None
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
        if ftp:
            ftp.quit()


def download(conanfile, url, filename, verify=True, retry=None, retry_wait=None,
             auth=None, headers=None, md5='', sha1='', sha256=''):
    """Retrieves a file from a given URL into a file with a given filename.
       It uses certificates from a list of known verifiers for https downloads,
       but this can be optionally disabled.

    :param conanfile:
    :param url: URL to download. It can be a list, which only the first one will be downloaded, and
                the follow URLs will be used as mirror in case of download error.
    :param filename: Name of the file to be created in the local storage
    :param verify: When False, disables https certificate validation
    :param retry: Number of retries in case of failure. Default is overriden by general.retry in the
                  conan.conf file or an env variable CONAN_RETRY
    :param retry_wait: Seconds to wait between download attempts. Default is overriden by
                       general.retry_wait in the conan.conf file or an env variable CONAN_RETRY_WAIT
    :param auth: A tuple of user and password to use HTTPBasic authentication
    :param headers: A dictionary with additional headers
    :param md5: MD5 hash code to check the downloaded file
    :param sha1: SHA-1 hash code to check the downloaded file
    :param sha256: SHA-256 hash code to check the downloaded file
    :return: None
    """
    # TODO: Add all parameters to the new conf
    out = conanfile.output
    requester = conanfile._conan_requester
    config = conanfile.conf
    overwrite = True

    if config["tools.files.download:retry"]:
        retry = int(config["tools.files.download:retry"])
    elif retry is None:
        retry = 1

    if config["tools.files.download:retry_wait"]:
        retry_wait = int(config["tools.files.download:retry_wait"])
    elif retry_wait is None:
        retry_wait = 5

    checksum = sha256 or sha1 or md5
    download_cache = config["tools.files.download:download_cache"] if checksum else None

    def _download_file(file_url):
        # The download cache is only used if a checksum is provided, otherwise, a normal download
        run_downloader(requester=requester, output=out, verify=verify, download_cache=download_cache,
                       user_download=True, url=file_url,
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


def rename(conanfile, src, dst):
    """
    rename a file or folder to avoid "Access is denied" error on Windows
    :param conanfile: conanfile object
    :param src: Source file or folder
    :param dst: Destination file or folder
    :return: None
    """
    # FIXME: This function has been copied from legacy. Needs to fix: which() call and wrap subprocess call.
    if os.path.exists(dst):
        raise ConanException("rename {} to {} failed, dst exists.".format(src, dst))

    if platform.system() == "Windows" and which("robocopy") and os.path.isdir(src):
        # /move Moves files and directories, and deletes them from the source after they are copied.
        # /e Copies subdirectories. Note that this option includes empty directories.
        # /ndl Specifies that directory names are not to be logged.
        # /nfl Specifies that file names are not to be logged.
        process = subprocess.Popen(["robocopy", "/move", "/e", "/ndl", "/nfl", src, dst],
                                   stdout=subprocess.PIPE)
        process.communicate()
        if process.returncode > 7:  # https://ss64.com/nt/robocopy-exit.html
            raise ConanException("rename {} to {} failed.".format(src, dst))
    else:
        try:
            os.rename(src, dst)
        except Exception as err:
            raise ConanException("rename {} to {} failed: {}".format(src, dst, err))


def load_toolchain_args(generators_folder=None, namespace=None):
    """
    Helper function to load the content of any CONAN_TOOLCHAIN_ARGS_FILE

    :param generators_folder: `str` folder where is located the CONAN_TOOLCHAIN_ARGS_FILE.
    :param namespace: `str` namespace to be prepended to the filename.
    :return: <class 'configparser.SectionProxy'>
    """
    namespace_name = "{}_{}".format(namespace, CONAN_TOOLCHAIN_ARGS_FILE) if namespace \
        else CONAN_TOOLCHAIN_ARGS_FILE
    args_file = os.path.join(generators_folder, namespace_name) if generators_folder \
        else namespace_name
    toolchain_config = configparser.ConfigParser()
    toolchain_file = toolchain_config.read(args_file)
    if not toolchain_file:
        raise ConanException("The file %s does not exist. Please, make sure that it was not"
                             " generated in another folder." % args_file)
    try:
        return toolchain_config[CONAN_TOOLCHAIN_ARGS_SECTION]
    except KeyError:
        raise ConanException("The primary section [%s] does not exist in the file %s. Please, add it"
                             " as the default one of all your configuration variables." %
                             (CONAN_TOOLCHAIN_ARGS_SECTION, args_file))


def save_toolchain_args(content, generators_folder=None, namespace=None):
    """
    Helper function to save the content into the CONAN_TOOLCHAIN_ARGS_FILE

    :param content: `dict` all the information to be saved into the toolchain file.
    :param namespace: `str` namespace to be prepended to the filename.
    :param generators_folder: `str` folder where is located the CONAN_TOOLCHAIN_ARGS_FILE
    """
    # Let's prune None values
    content_ = {k: v for k, v in content.items() if v is not None}
    namespace_name = "{}_{}".format(namespace, CONAN_TOOLCHAIN_ARGS_FILE) if namespace \
        else CONAN_TOOLCHAIN_ARGS_FILE
    args_file = os.path.join(generators_folder, namespace_name) if generators_folder \
        else namespace_name
    toolchain_config = configparser.ConfigParser()
    toolchain_config[CONAN_TOOLCHAIN_ARGS_SECTION] = content_
    with open(args_file, "w") as f:
        toolchain_config.write(f)


@contextmanager
def chdir(conanfile, newdir):
    old_path = os.getcwd()
    os.chdir(newdir)
    try:
        yield
    finally:
        os.chdir(old_path)
