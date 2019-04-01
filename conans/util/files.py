import errno
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


def make_read_only(path):
    for root, _, files in walk(path):
        for f in files:
            full_path = os.path.join(root, f)
            mode = os.stat(full_path).st_mode
            os.chmod(full_path, mode & ~ stat.S_IWRITE)


_DIRTY_FOLDER = ".dirty"


def set_dirty(folder):
    dirty_file = os.path.normpath(folder) + _DIRTY_FOLDER
    save(dirty_file, "")


def clean_dirty(folder):
    dirty_file = os.path.normpath(folder) + _DIRTY_FOLDER
    os.remove(dirty_file)


def is_dirty(folder):
    dirty_file = os.path.normpath(folder) + _DIRTY_FOLDER
    return os.path.exists(dirty_file)


def decode_text(text):
    decoders = ["utf-8", "Windows-1252"]
    for decoder in decoders:
        try:
            return text.decode(decoder)
        except UnicodeDecodeError:
            continue
    logger.warning("can't decode %s" % str(text))
    return text.decode("utf-8", "ignore")  # Ignore not compatible characters


def touch(fname, times=None):
    os.utime(fname, times)


def touch_folder(folder):
    for dirname, _, filenames in walk(folder):
        for fname in filenames:
            os.utime(os.path.join(dirname, fname), None)


def normalize(text):
    if platform.system() == "Windows":
        return re.sub("\r?\n", "\r\n", text)
    else:
        return text


def md5(content):
    md5alg = hashlib.md5()
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
        m = hashlib.new(algorithm_name)
        while True:
            data = fh.read(8192)
            if not data:
                break
            m.update(data)
        return m.hexdigest()


def save_append(path, content):
    try:
        os.makedirs(os.path.dirname(path))
    except:
        pass

    with open(path, "ab") as handle:
        handle.write(to_file_bytes(content))


def save(path, content, only_if_modified=False):
    """
    Saves a file with given content
    Params:
        path: path to write file to
        content: contents to save in the file
        only_if_modified: file won't be modified if the content hasn't changed
    """
    try:
        os.makedirs(os.path.dirname(path))
    except:
        pass

    new_content = to_file_bytes(content)

    if only_if_modified and os.path.exists(path):
        old_content = load(path, binary=True)
        if old_content == new_content:
            return

    with open(path, "wb") as handle:
        handle.write(new_content)


def mkdir_tmp():
    return tempfile.mkdtemp(suffix='tmp_conan')


def to_file_bytes(content):
    if six.PY3:
        if not isinstance(content, bytes):
            content = bytes(content, "utf-8")
    elif isinstance(content, unicode):
        content = content.encode("utf-8")
    return content


def save_files(path, files, only_if_modified=False):
    for name, content in list(files.items()):
        save(os.path.join(path, name), content, only_if_modified=only_if_modified)


def load(path, binary=False):
    """ Loads a file content """
    with open(path, 'rb') as handle:
        tmp = handle.read()
        return tmp if binary else decode_text(tmp)


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


def gzopen_without_timestamps(name, mode="r", fileobj=None, compresslevel=None, **kwargs):
    """ !! Method overrided by laso to pass mtime=0 (!=None) to avoid time.time() was
        setted in Gzip file causing md5 to change. Not possible using the
        previous tarfile open because arguments are not passed to GzipFile constructor
    """
    from tarfile import CompressionError, ReadError

    compresslevel = compresslevel or int(os.getenv("CONAN_COMPRESSION_LEVEL", 9))

    if mode not in ("r", "w"):
        raise ValueError("mode must be 'r' or 'w'")

    try:
        import gzip
        gzip.GzipFile
    except (ImportError, AttributeError):
        raise CompressionError("gzip module is not available")

    try:
        fileobj = gzip.GzipFile(name, mode, compresslevel, fileobj, mtime=0)
    except OSError:
        if fileobj is not None and mode == 'r':
            raise ReadError("not a gzip file")
        raise

    try:
        t = tarfile.TarFile.taropen(name, mode, fileobj, **kwargs)
    except IOError:
        fileobj.close()
        if mode == 'r':
            raise ReadError("not a gzip file")
        raise
    except:
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
        base = realpath(abspath("."))

        for finfo in members:
            if badpath(finfo.name, base) or finfo.islnk():
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
    except:
        return decode_text(repr(exc))
