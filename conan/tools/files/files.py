import configparser
import errno
import gzip
import hashlib
import os
import platform
import shutil
import subprocess
import sys
from contextlib import contextmanager
from fnmatch import fnmatch

import six
from urllib.parse import urlparse
from urllib.request import url2pathname

from conan.tools import CONAN_TOOLCHAIN_ARGS_FILE, CONAN_TOOLCHAIN_ARGS_SECTION
from conans.client.downloaders.download import run_downloader
from conans.errors import ConanException
from conans.util.files import rmdir as _internal_rmdir
from conans.util.runners import check_output_runner

if six.PY3:  # Remove this IF in develop2
    from shutil import which


def load(conanfile, path, encoding="utf-8"):
    """ Loads a file content """
    with open(path, 'rb') as handle:
        tmp = handle.read()
        return tmp.decode(encoding)


def save(conanfile, path, content, append=False, encoding="utf-8"):
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
        if not isinstance(content, bytes):
            content = bytes(content, encoding=encoding)
        handle.write(content)


def mkdir(conanfile, path):
    """Recursive mkdir, doesnt fail if already existing"""
    if os.path.exists(path):
        return
    os.makedirs(path)


def rmdir(conanfile, path):
    _internal_rmdir(path)


def rm(conanfile, pattern, folder, recursive=False):
    for root, _, filenames in os.walk(folder):
        for filename in filenames:
            if fnmatch(filename, pattern):
                fullname = os.path.join(root, filename)
                os.unlink(fullname)
        if not recursive:
            break


def get(conanfile, url, md5=None, sha1=None, sha256=None, destination=".", filename="",
        keep_permissions=False, pattern=None, verify=True, retry=None, retry_wait=None,
        auth=None, headers=None, strip_root=False):
    """ high level downloader + unzipper + (optional hash checker) + delete temporary zip
    """

    if not filename:  # deduce filename from the URL
        url_base = url[0] if isinstance(url, (list, tuple)) else url
        if "?" in url_base or "=" in url_base:
            raise ConanException("Cannot deduce file name from the url: '{}'. Use 'filename' "
                                 "parameter.".format(url_base))
        filename = os.path.basename(url_base)

    download(conanfile, url, filename, verify=verify,
             retry=retry, retry_wait=retry_wait, auth=auth, headers=headers,
             md5=md5, sha1=sha1, sha256=sha256)
    unzip(conanfile, filename, destination=destination, keep_permissions=keep_permissions,
          pattern=pattern, strip_root=strip_root)
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
             auth=None, headers=None, md5=None, sha1=None, sha256=None):
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
        if file_url.startswith("file:"):
            _copy_local_file_from_uri(conanfile, url=file_url, file_path=filename, md5=md5,
                                      sha1=sha1, sha256=sha256)
        else:
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


def _copy_local_file_from_uri(conanfile, url, file_path, md5=None, sha1=None, sha256=None):
    file_origin = _path_from_file_uri(url)
    shutil.copyfile(file_origin, file_path)

    if md5 is not None:
        check_md5(conanfile, file_path, md5)
    if sha1 is not None:
        check_sha1(conanfile, file_path, sha1)
    if sha256 is not None:
        check_sha256(conanfile, file_path, sha256)


def _path_from_file_uri(uri):
    path = urlparse(uri).path
    return url2pathname(path)


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


def unzip(conanfile, filename, destination=".", keep_permissions=False, pattern=None,
          strip_root=False):
    """
    Unzip a zipped file
    :param filename: Path to the zip file
    :param destination: Destination folder (or file for .gz files)
    :param keep_permissions: Keep the zip permissions. WARNING: Can be
    dangerous if the zip was not created in a NIX system, the bits could
    produce undefined permission schema. Use this option only if you are sure
    that the zip was created correctly.
    :param pattern: Extract only paths matching the pattern. This should be a
    Unix shell-style wildcard, see fnmatch documentation for more details.
    :param flat: If all the contents are in a single dir, flat that directory.
    :return:
    """

    output = conanfile.output
    if (filename.endswith(".tar.gz") or filename.endswith(".tgz") or
            filename.endswith(".tbz2") or filename.endswith(".tar.bz2") or
            filename.endswith(".tar")):
        return untargz(filename, destination, pattern, strip_root)
    if filename.endswith(".gz"):
        with gzip.open(filename, 'rb') as f:
            file_content = f.read()
        target_name = filename[:-3] if destination == "." else destination
        save(conanfile, target_name, file_content)
        return
    if filename.endswith(".tar.xz") or filename.endswith(".txz"):
        return untargz(filename, destination, pattern, strip_root)

    import zipfile
    full_path = os.path.normpath(os.path.join(os.getcwd(), destination))

    if hasattr(sys.stdout, "isatty") and sys.stdout.isatty():
        def print_progress(the_size, uncomp_size):
            the_size = (the_size * 100.0 / uncomp_size) if uncomp_size != 0 else 0
            txt_msg = "Unzipping %d %%"
            if the_size > print_progress.last_size + 1:
                output.rewrite_line(txt_msg % the_size)
                print_progress.last_size = the_size
                if int(the_size) == 99:
                    output.rewrite_line(txt_msg % 100)
    else:
        def print_progress(_, __):
            pass

    with zipfile.ZipFile(filename, "r") as z:
        zip_info = z.infolist()
        if pattern:
            zip_info = [zi for zi in zip_info if fnmatch(zi.filename, pattern)]
        if strip_root:
            names = [n.replace("\\", "/") for n in z.namelist()]
            common_folder = os.path.commonprefix(names).split("/", 1)[0]
            if not common_folder and len(names) > 1:
                raise ConanException("The zip file contains more than 1 folder in the root")
            if len(names) == 1 and len(names[0].split("/", 1)) == 1:
                raise ConanException("The zip file contains a file in the root")
            # Remove the directory entry if present
            # Note: The "zip" format contains the "/" at the end if it is a directory
            zip_info = [m for m in zip_info if m.filename != (common_folder + "/")]
            for member in zip_info:
                name = member.filename.replace("\\", "/")
                member.filename = name.split("/", 1)[1]

        uncompress_size = sum((file_.file_size for file_ in zip_info))
        if uncompress_size > 100000:
            output.info("Unzipping %s, this can take a while" % _human_size(uncompress_size))
        else:
            output.info("Unzipping %s" % _human_size(uncompress_size))
        extracted_size = 0

        print_progress.last_size = -1
        if platform.system() == "Windows":
            for file_ in zip_info:
                extracted_size += file_.file_size
                print_progress(extracted_size, uncompress_size)
                try:
                    z.extract(file_, full_path)
                except Exception as e:
                    output.error("Error extract %s\n%s" % (file_.filename, str(e)))
        else:  # duplicated for, to avoid a platform check for each zipped file
            for file_ in zip_info:
                extracted_size += file_.file_size
                print_progress(extracted_size, uncompress_size)
                try:
                    z.extract(file_, full_path)
                    if keep_permissions:
                        # Could be dangerous if the ZIP has been created in a non nix system
                        # https://bugs.python.org/issue15795
                        perm = file_.external_attr >> 16 & 0xFFF
                        os.chmod(os.path.join(full_path, file_.filename), perm)
                except Exception as e:
                    output.error("Error extract %s\n%s" % (file_.filename, str(e)))
        output.writeln("")


def untargz(filename, destination=".", pattern=None, strip_root=False):
    # NOT EXPOSED at `conan.tools.files` but used in tests
    import tarfile
    with tarfile.TarFile.open(filename, 'r:*') as tarredgzippedFile:
        if not pattern and not strip_root:
            tarredgzippedFile.extractall(destination)
        else:
            members = tarredgzippedFile.getmembers()

            if strip_root:
                names = [n.replace("\\", "/") for n in tarredgzippedFile.getnames()]
                common_folder = os.path.commonprefix(names).split("/", 1)[0]
                if not common_folder and len(names) > 1:
                    raise ConanException("The tgz file contains more than 1 folder in the root")
                if len(names) == 1 and len(names[0].split("/", 1)) == 1:
                    raise ConanException("The tgz file contains a file in the root")
                # Remove the directory entry if present
                members = [m for m in members if m.name != common_folder]
                for member in members:
                    name = member.name.replace("\\", "/")
                    member.name = name.split("/", 1)[1]
                    member.path = member.name
                    if member.linkpath.startswith(common_folder):
                        # https://github.com/conan-io/conan/issues/11065
                        linkpath = member.linkpath.replace("\\", "/")
                        member.linkpath = linkpath.split("/", 1)[1]
                        member.linkname = member.linkpath
            if pattern:
                members = list(filter(lambda m: fnmatch(m.name, pattern),
                                      tarredgzippedFile.getmembers()))
            tarredgzippedFile.extractall(destination, members=members)


def _human_size(size_bytes):
    """
    format a size in bytes into a 'human' file size, e.g. B, KB, MB, GB, TB, PB
    Note that bytes will be reported in whole numbers but KB and above will have
    greater precision.  e.g. 43 B, 443 KB, 4.3 MB, 4.43 GB, etc
    """
    UNIT_SIZE = 1000.0

    suffixes_table = [('B', 0), ('KB', 1), ('MB', 1), ('GB', 2), ('TB', 2), ('PB', 2)]

    num = float(size_bytes)
    the_precision = None
    the_suffix = None
    for suffix, precision in suffixes_table:
        the_precision = precision
        the_suffix = suffix
        if num < UNIT_SIZE:
            break
        num /= UNIT_SIZE

    if the_precision == 0:
        formatted_size = "%d" % num
    else:
        formatted_size = str(round(num, ndigits=the_precision))

    return "%s%s" % (formatted_size, the_suffix)


def check_sha1(conanfile, file_path, signature):
    _check_with_algorithm_sum("sha1", file_path, signature)


def check_md5(conanfile, file_path, signature):
    _check_with_algorithm_sum("md5", file_path, signature)


def check_sha256(conanfile, file_path, signature):
    _check_with_algorithm_sum("sha256", file_path, signature)


def _check_with_algorithm_sum(algorithm_name, file_path, signature):
    real_signature = _generic_algorithm_sum(file_path, algorithm_name)
    if real_signature != signature.lower():
        raise ConanException("%s signature failed for '%s' file. \n"
                             " Provided signature: %s  \n"
                             " Computed signature: %s" % (algorithm_name,
                                                          os.path.basename(file_path),
                                                          signature,
                                                          real_signature))


def _generic_algorithm_sum(file_path, algorithm_name):

    with open(file_path, 'rb') as fh:
        try:
            m = hashlib.new(algorithm_name)
        except ValueError:  # FIPS error https://github.com/conan-io/conan/issues/7800
            m = hashlib.new(algorithm_name, usedforsecurity=False)
        while True:
            data = fh.read(8192)
            if not data:
                break
            m.update(data)
        return m.hexdigest()


def replace_in_file(conanfile, file_path, search, replace, strict=True, encoding="utf-8"):
    """
    :param conanfile: Conanfile instance
    :param file_path: Path to the file
    :param search: Pattern to search
    :param replace: string to replace the matches
    :param strict: Raise in case "search" is not found in the file contents
    :return:
    """
    output = conanfile.output
    content = load(conanfile, file_path, encoding=encoding)
    if -1 == content.find(search):
        message = "replace_in_file didn't find pattern '%s' in '%s' file." % (search, file_path)
        if strict:
            raise ConanException(message)
        else:
            output.warn(message)
            return False
    content = content.replace(search, replace)
    save(conanfile, file_path, content, encoding=encoding)


def collect_libs(conanfile, folder=None):
    if not conanfile.package_folder:
        return []
    if folder:
        lib_folders = [os.path.join(conanfile.package_folder, folder)]
    else:
        lib_folders = [os.path.join(conanfile.package_folder, folder)
                       for folder in conanfile.cpp_info.libdirs]

    ref_libs = {}
    for lib_folder in lib_folders:
        if not os.path.exists(lib_folder):
            conanfile.output.warn("Lib folder doesn't exist, can't collect libraries: "
                                  "{0}".format(lib_folder))
            continue
        # In case of symlinks, only keep shortest file name in the same "group"
        files = os.listdir(lib_folder)
        for f in files:
            name, ext = os.path.splitext(f)
            if ext in (".so", ".lib", ".a", ".dylib", ".bc"):
                real_lib = os.path.basename(os.path.realpath(os.path.join(lib_folder, f)))
                if real_lib not in ref_libs or len(f) < len(ref_libs[real_lib]):
                    ref_libs[real_lib] = f

    result = []
    for f in ref_libs.values():
        name, ext = os.path.splitext(f)
        if ext != ".lib" and name.startswith("lib"):
            name = name[3:]
        if name not in result:
            result.append(name)
    result.sort()
    return result


# TODO: Do NOT document this yet. It is unclear the interface, maybe should be split
def swap_child_folder(parent_folder, child_folder):
    """ replaces the current folder contents with the contents of one child folder. This
    is used in the SCM monorepo flow, when it is necessary to use one subproject subfolder
    to replace the whole cloned git repo
    """
    for f in os.listdir(parent_folder):
        if f != child_folder:
            path = os.path.join(parent_folder, f)
            if os.path.isfile(path):
                os.remove(path)
            else:
                _internal_rmdir(path)
    child = os.path.join(parent_folder, child_folder)
    for f in os.listdir(child):
        shutil.move(os.path.join(child, f), os.path.join(parent_folder, f))
