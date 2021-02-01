import errno
import gzip
import hashlib
import os
import platform
import re
import shutil
import stat
import sys
import tarfile
import tempfile


from os.path import abspath, join as joinpath, realpath
from contextlib import contextmanager

import six

from conans.util.log import logger


def walk(top, **kwargs):
    if six.PY2:
        # If py2 os.walk receives a unicode object, it will fail if a non-ascii file name is found
        # during the iteration. More info:
        # https://stackoverflow.com/questions/21772271/unicodedecodeerror-when-performing-os-walk
        try:
            top = str(top)
        except UnicodeDecodeError:
            pass

    return os.walk(top, **kwargs)


def make_read_only(folder_path):
    for root, _, files in walk(folder_path):
        for f in files:
            full_path = os.path.join(root, f)
            make_file_read_only(full_path)


def make_file_read_only(file_path):
    mode = os.stat(file_path).st_mode
    os.chmod(file_path, mode & ~ stat.S_IWRITE)


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


def decode_text(text, encoding="auto"):
    bom_length = 0
    if encoding == "auto":
        encoding, bom_length = _detect_encoding(text)
        if encoding is None:
            logger.warning("can't decode %s" % str(text))
            return text.decode("utf-8", "ignore")  # Ignore not compatible characters
    return text[bom_length:].decode(encoding)


def touch(fname, times=None):
    os.utime(fname, times)


def touch_folder(folder):
    for dirname, _, filenames in walk(folder):
        for fname in filenames:
            try:
                os.utime(os.path.join(dirname, fname), None)
            except Exception:
                pass


def normalize(text):
    if platform.system() == "Windows":
        return re.sub("\r?\n", "\r\n", text)
    else:
        return text


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
    if six.PY3:
        if not isinstance(content, bytes):
            content = bytes(content, encoding)
    elif isinstance(content, unicode):
        content = content.encode(encoding)
    return content


def save_files(path, files, only_if_modified=False, encoding="utf-8"):
    for name, content in files.items():
        save(os.path.join(path, name), content, only_if_modified=only_if_modified, encoding=encoding)


def load(path, binary=False, encoding="auto"):
    """ Loads a file content """
    with open(path, 'rb') as handle:
        tmp = handle.read()
        return tmp if binary else decode_text(tmp, encoding)


def relative_dirs(path):
    """ Walks a dir and return a list with the relative paths """
    ret = []
    for dirpath, _, fnames in walk(path):
        for filename in fnames:
            tmp = os.path.join(dirpath, filename)
            tmp = tmp[len(path) + 1:]
            ret.append(tmp)
    return ret


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


def path_exists(path, basedir):
    """Case sensitive, for windows, optional
    basedir for skip caps check for tmp folders in testing for example (returned always
    in lowercase for some strange reason)"""
    exists = os.path.exists(path)
    if not exists or sys.platform == "linux2":
        return exists

    path = os.path.normpath(path)
    path = os.path.relpath(path, basedir)
    chunks = path.split(os.sep)
    tmp = basedir

    for chunk in chunks:
        if chunk and chunk not in os.listdir(tmp):
            return False
        tmp = os.path.normpath(tmp + os.sep + chunk)
    return True


def gzopen_without_timestamps(name, mode="r", fileobj=None, **kwargs):
    """ !! Method overrided by laso to pass mtime=0 (!=None) to avoid time.time() was
        setted in Gzip file causing md5 to change. Not possible using the
        previous tarfile open because arguments are not passed to GzipFile constructor
    """
    compresslevel = int(os.getenv("CONAN_COMPRESSION_LEVEL", 9))

    if mode not in ("r", "w"):
        raise ValueError("mode must be 'r' or 'w'")

    try:
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
            if badpath(finfo.name, base) or finfo.islnk():
                logger.warning("file:%s is skipped since it's not safe." % str(finfo.name))
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


def list_folder_subdirs(basedir, level):
    ret = []
    for root, dirs, _ in walk(basedir):
        rel_path = os.path.relpath(root, basedir)
        if rel_path == ".":
            continue
        dir_split = rel_path.split(os.sep)
        if len(dir_split) == level:
            ret.append("/".join(dir_split))
            dirs[:] = []  # Stop iterate subdirs
    return ret


def exception_message_safe(exc):
    try:
        return str(exc)
    except Exception:
        return decode_text(repr(exc))


def merge_directories(src, dst, excluded=None):
    src = os.path.normpath(src)
    dst = os.path.normpath(dst)
    excluded = excluded or []
    excluded = [os.path.normpath(entry) for entry in excluded]

    def is_excluded(origin_path):
        if origin_path == dst:
            return True
        rel_path = os.path.normpath(os.path.relpath(origin_path, src))
        if rel_path in excluded:
            return True
        return False

    def link_to_rel(pointer_src):
        linkto = os.readlink(pointer_src)
        if not os.path.isabs(linkto):
            linkto = os.path.join(os.path.dirname(pointer_src), linkto)

        # Check if it is outside the sources
        out_of_source = os.path.relpath(linkto, os.path.realpath(src)).startswith(".")
        if out_of_source:
            # May warn about out of sources symlink
            return

        # Create the symlink
        linkto_rel = os.path.relpath(linkto, os.path.dirname(pointer_src))
        pointer_dst = os.path.normpath(os.path.join(dst, os.path.relpath(pointer_src, src)))
        os.symlink(linkto_rel, pointer_dst)

    for src_dir, dirs, files in walk(src, followlinks=True):
        if is_excluded(src_dir):
            dirs[:] = []
            continue

        if os.path.islink(src_dir):
            link_to_rel(src_dir)
            dirs[:] = []  # Do not enter subdirectories
            continue

        # Overwriting the dirs will prevents walk to get into them
        files[:] = [d for d in files if not is_excluded(os.path.join(src_dir, d))]

        dst_dir = os.path.normpath(os.path.join(dst, os.path.relpath(src_dir, src)))
        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir)
        for file_ in files:
            src_file = os.path.join(src_dir, file_)
            dst_file = os.path.join(dst_dir, file_)
            if os.path.islink(src_file):
                link_to_rel(src_file)
            else:
                shutil.copy2(src_file, dst_file)
