import errno
import gzip
import hashlib
import os
import shutil
import stat
import tarfile
import tempfile


from os.path import abspath, join as joinpath, realpath
from contextlib import contextmanager


_DIRTY_FOLDER = ".dirty"


def set_dirty(folder):
    dirty_file = os.path.normpath(folder) + _DIRTY_FOLDER
    assert not os.path.exists(dirty_file), "Folder '{}' is already dirty".format(folder)
    save(dirty_file, "")


def clean_dirty(folder):
    dirty_file = os.path.normpath(folder) + _DIRTY_FOLDER
    os.remove(dirty_file)


def is_dirty(folder):
    dirty_file = os.path.normpath(folder) + _DIRTY_FOLDER
    return os.path.exists(dirty_file)


@contextmanager
def set_dirty_context_manager(folder):
    set_dirty(folder)
    yield
    clean_dirty(folder)


def _detect_encoding(text):
    import codecs
    encodings = {codecs.BOM_UTF8: "utf_8_sig",
                 codecs.BOM_UTF16_BE: "utf_16_be",
                 codecs.BOM_UTF16_LE: "utf_16_le",
                 codecs.BOM_UTF32_BE: "utf_32_be",
                 codecs.BOM_UTF32_LE: "utf_32_le",
                 b'\x2b\x2f\x76\x38': "utf_7",
                 b'\x2b\x2f\x76\x39': "utf_7",
                 b'\x2b\x2f\x76\x2b': "utf_7",
                 b'\x2b\x2f\x76\x2f': "utf_7",
                 b'\x2b\x2f\x76\x38\x2d': "utf_7"}
    for bom in sorted(encodings, key=len, reverse=True):
        if text.startswith(bom):
            try:
                return encodings[bom], len(bom)
            except UnicodeDecodeError:
                continue
    decoders = ["utf-8", "Windows-1252"]
    for decoder in decoders:
        try:
            text.decode(decoder)
            return decoder, 0
        except UnicodeDecodeError:
            continue
    return None, 0


@contextmanager
def chdir(newdir):
    old_path = os.getcwd()
    os.chdir(newdir)
    try:
        yield
    finally:
        os.chdir(old_path)


def decode_text(text, encoding="auto"):
    bom_length = 0
    if encoding == "auto":
        encoding, bom_length = _detect_encoding(text)
        if encoding is None:
            return text.decode("utf-8", "ignore")  # Ignore not compatible characters
    return text[bom_length:].decode(encoding)


def touch(fname, times=None):
    os.utime(fname, times)


def touch_folder(folder):
    for dirname, _, filenames in os.walk(folder):
        for fname in filenames:
            try:
                os.utime(os.path.join(dirname, fname), None)
            except Exception:
                pass


def md5(content):
    try:
        md5alg = hashlib.md5()
    except ValueError:  # FIPS error https://github.com/conan-io/conan/issues/7800
        md5alg = hashlib.md5(usedforsecurity=False)
    if isinstance(content, bytes):
        tmp = content
    else:
        tmp = content.encode("utf-8")
    md5alg.update(tmp)
    return md5alg.hexdigest()


def md5sum(file_path):
    return _generic_algorithm_sum(file_path, "md5")


def sha1sum(file_path):
    return _generic_algorithm_sum(file_path, "sha1")


def sha256sum(file_path):
    return _generic_algorithm_sum(file_path, "sha256")


# FIXME: Duplicated with util/sha.py
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


def save_append(path, content, encoding="utf-8"):
    try:
        os.makedirs(os.path.dirname(path))
    except Exception:
        pass

    with open(path, "ab") as handle:
        handle.write(to_file_bytes(content, encoding=encoding))


def save(path, content, only_if_modified=False, encoding="utf-8"):
    """
    Saves a file with given content
    Params:
        path: path to write file to
        content: contents to save in the file
        only_if_modified: file won't be modified if the content hasn't changed
        encoding: target file text encoding
    """
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

    new_content = to_file_bytes(content, encoding)

    if only_if_modified and os.path.exists(path):
        old_content = load(path, binary=True, encoding=encoding)
        if old_content == new_content:
            return

    with open(path, "wb") as handle:
        handle.write(new_content)


def mkdir_tmp():
    return tempfile.mkdtemp(suffix='tmp_conan')


def to_file_bytes(content, encoding="utf-8"):
    if not isinstance(content, bytes):
        content = bytes(content, encoding)
    return content


def save_files(path, files, only_if_modified=False, encoding="utf-8"):
    for name, content in files.items():
        save(os.path.join(path, name), content, only_if_modified=only_if_modified, encoding=encoding)


def load(path, binary=False, encoding="auto"):
    """ Loads a file content """
    with open(path, 'rb') as handle:
        tmp = handle.read()
        return tmp if binary else decode_text(tmp, encoding)


def get_abs_path(folder, origin):
    if folder:
        if os.path.isabs(folder):
            return folder
        return os.path.join(origin, folder)
    return origin


def _change_permissions(func, path, exc_info):
    if not os.access(path, os.W_OK):
        os.chmod(path, stat.S_IWUSR)
        func(path)
    else:
        raise OSError("Cannot change permissions for {}! Exception info: {}".format(path, exc_info))


def rmdir(path):
    try:
        shutil.rmtree(path, onerror=_change_permissions)
    except OSError as err:
        if err.errno == errno.ENOENT:
            return
        raise


def remove(path):
    try:
        assert os.path.isfile(path)
        os.remove(path)
    except (IOError, OSError) as e:  # for py3, handle just PermissionError
        if e.errno == errno.EPERM or e.errno == errno.EACCES:
            os.chmod(path, stat.S_IRWXU)
            os.remove(path)
            return
        raise


def mkdir(path):
    """Recursive mkdir, doesnt fail if already existing"""
    if os.path.exists(path):
        return
    os.makedirs(path)


def gzopen_without_timestamps(name, mode="r", fileobj=None, compresslevel=None, **kwargs):
    """ !! Method overrided by laso to pass mtime=0 (!=None) to avoid time.time() was
        setted in Gzip file causing md5 to change. Not possible using the
        previous tarfile open because arguments are not passed to GzipFile constructor
    """

    if mode not in ("r", "w"):
        raise ValueError("mode must be 'r' or 'w'")

    try:
        compresslevel = compresslevel if compresslevel is not None else 9  # default Gzip = 9
        fileobj = gzip.GzipFile(name, mode, compresslevel, fileobj, mtime=0)
    except OSError:
        if fileobj is not None and mode == 'r':
            raise tarfile.ReadError("not a gzip file")
        raise

    try:
        # Format is forced because in Python3.8, it changed and it generates different tarfiles
        # with different checksums, which break hashes of tgzs
        t = tarfile.TarFile.taropen(name, mode, fileobj, format=tarfile.GNU_FORMAT, **kwargs)
    except IOError:
        fileobj.close()
        if mode == 'r':
            raise tarfile.ReadError("not a gzip file")
        raise
    except Exception:
        fileobj.close()
        raise
    t._extfileobj = False
    return t


def tar_extract(fileobj, destination_dir):
    """Extract tar file controlling not absolute paths and fixing the routes
    if the tar was zipped in windows"""
    def badpath(path, base):
        # joinpath will ignore base if path is absolute
        return not realpath(abspath(joinpath(base, path))).startswith(base)

    def safemembers(members):
        base = realpath(abspath(destination_dir))

        for finfo in members:
            if badpath(finfo.name, base):
                # ConanOutput().warning("file:%s is skipped since it's not safe." % str(finfo.name))
                continue
            else:
                # Fixes unzip a windows zipped file in linux
                finfo.name = finfo.name.replace("\\", "/")
                yield finfo

    the_tar = tarfile.open(fileobj=fileobj)
    # NOTE: The errorlevel=2 has been removed because it was failing in Win10, it didn't allow to
    # "could not change modification time", with time=0
    # the_tar.errorlevel = 2  # raise exception if any error
    the_tar.extractall(path=destination_dir, members=safemembers(the_tar))
    the_tar.close()


def exception_message_safe(exc):
    try:
        return str(exc)
    except Exception:
        return decode_text(repr(exc))


def merge_directories(src, dst, excluded=None):
    from conan.tools.files import copy
    copy(None, pattern="*", src=src, dst=dst, excludes=excluded)
    return


def discarded_file(filename):
    """
    # The __conan pattern is to be prepared for the future, in case we want to manage our
    own files that shouldn't be uploaded
    """
    return filename == ".DS_Store" or filename.startswith("__conan")


def gather_files(folder):
    file_dict = {}
    symlinked_folders = {}
    for root, dirs, files in os.walk(folder):
        for d in dirs:
            abs_path = os.path.join(root, d)
            if os.path.islink(abs_path):
                rel_path = abs_path[len(folder) + 1:].replace("\\", "/")
                symlinked_folders[rel_path] = abs_path
                continue
        for f in files:
            if discarded_file(f):
                continue
            abs_path = os.path.join(root, f)
            rel_path = abs_path[len(folder) + 1:].replace("\\", "/")
            file_dict[rel_path] = abs_path

    return file_dict, symlinked_folders


# FIXME: This is very repeated with the tools.unzip, but wsa needed for config-install unzip
def unzip(filename, destination="."):
    from conan.tools.files.files import untargz  # FIXME, importing from conan.tools
    if (filename.endswith(".tar.gz") or filename.endswith(".tgz") or
            filename.endswith(".tbz2") or filename.endswith(".tar.bz2") or
            filename.endswith(".tar")):
        return untargz(filename, destination)
    if filename.endswith(".gz"):
        with gzip.open(filename, 'rb') as f:
            file_content = f.read()
        target_name = filename[:-3] if destination == "." else destination
        save(target_name, file_content)
        return
    if filename.endswith(".tar.xz") or filename.endswith(".txz"):
        return untargz(filename, destination)

    import zipfile
    full_path = os.path.normpath(os.path.join(os.getcwd(), destination))

    with zipfile.ZipFile(filename, "r") as z:
        zip_info = z.infolist()
        extracted_size = 0
        for file_ in zip_info:
            extracted_size += file_.file_size
            z.extract(file_, full_path)
