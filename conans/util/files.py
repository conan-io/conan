import os
import shutil
from errno import ENOENT, EEXIST
import hashlib
import sys
import tarfile
from os.path import abspath, realpath, join as joinpath
import platform
import re

def delete_empty_dirs(folder):
    for root, _, _ in os.walk(folder, topdown=False):
        try:  # Take advantage that os.rmdir does not delete non-empty dirs
            os.rmdir(root)
        except OSError:
            pass  # not empty

            
def normalize(text):
    if platform.system() == "Windows":
        return re.sub("\r?\n", "\r\n", text)
    else:
        return text


def md5(content):
    md5alg = hashlib.md5()
    md5alg.update(content)
    return md5alg.hexdigest()


def md5sum(file_path):
    return _generic_algorithm_sum(file_path, "md5")


def _generic_algorithm_sum(file_path, algorithm_name):

    with open(file_path, 'rb') as fh:
        m = getattr(hashlib, algorithm_name)()
        while True:
            data = fh.read(8192)
            if not data:
                break
            m.update(data)
        return m.hexdigest()


def save(path, content):
    '''
    Saves a file with given content
    Params:
        path: path to write file to
        load: contents to save in the file
    '''
    try:
        os.makedirs(os.path.dirname(path))
    except:
        pass

    with open(path, 'wb') as handle:
        handle.write(content)


def save_files(path, files):
    for name, content in files.iteritems():
        save(os.path.join(path, name), content)


def load(path):
    '''Loads a file content'''
    with open(path, 'rb') as handle:
        return handle.read()


def build_files_set(basedir, rel_files):
    '''Builds a file dict keeping the relative path'''
    ret = {}
    for filename in rel_files:
        abs_path = os.path.join(basedir, filename)
        ret[filename] = load(abs_path)

    return ret


def relative_dirs(path):
    ''' Walks a dir and return a list with the relative paths '''
    ret = []
    for dirpath, _, fnames in os.walk(path):
        for filename in fnames:
            tmp = os.path.join(dirpath, filename)
            tmp = tmp[len(path) + 1:]
            ret.append(tmp)
    return ret


def _change_permissions(func, path, exc_info):
    import stat
    if not os.access(path, os.W_OK):
        os.chmod(path, stat.S_IWUSR)
        func(path)
    else:
        raise


def rmdir(path, raise_if_not_exist=False):
    '''Recursive rm of a directory. If dir not exists
    only raise exception if raise_if_not_exist'''
    try:
        shutil.rmtree(path, onerror=_change_permissions)
    except OSError as err:
        if err.errno == ENOENT and not raise_if_not_exist:
            return
        raise


def mkdir(path, raise_if_already_exists=False):
    """Recursive mkdir. If dir already exists
    only raise if raise_if_already_exists"""
    try:
        os.makedirs(path)
    except OSError as err:
        if err.errno == EEXIST and not raise_if_already_exists:
            return
        raise


def path_exists(path, basedir=None):
    """Case sensitive, for windows, optional
    basedir for skip caps check for tmp folders in testing for example (returned always
    in lowercase for some strange reason)"""
    exists = os.path.exists(path)
    if not exists or sys.platform == "linux2":
        return exists

    path = os.path.normpath(path)

    if basedir:
        path = os.path.relpath(path, basedir)
        chunks = path.split(os.sep)
        tmp = basedir
    else:
        chunks = path.split(os.sep)
        tmp = chunks[0]  # Skip unit (c:)
        chunks = chunks[1:]

    for chunk in chunks[0:]:
        tmp = tmp + os.sep
        if chunk and chunk not in os.listdir(tmp):
            return False
        tmp += chunk
    return True


def gzopen_without_timestamps(name, mode="r", fileobj=None, compresslevel=9, **kwargs):
    """ !! Method overrided by laso to pass mtime=0 (!=None) to avoid time.time() was 
        setted in Gzip file causing md5 to change. Not possible using the 
        previous tarfile open because arguments are not passed to GzipFile constructor
    """
    from tarfile import CompressionError, ReadError
    import tarfile

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
    '''Extract tar file controlling not absolute paths and fixing the routes
    if the tar was zipped in windows'''
    def badpath(path, base):
        # joinpath will ignore base if path is absolute
        return not realpath(abspath(joinpath(base, path))).startswith(base)

    def safemembers(members):
        base = realpath(abspath("."))

        for finfo in members:
            if badpath(finfo.name, base) or finfo.issym() or finfo.islnk():
                continue
            else:
                # Fixes unzip a windows zipped file in linux
                finfo.name = finfo.name.replace("\\", "/")
                yield finfo

    the_tar = tarfile.open(fileobj=fileobj)
    the_tar.extractall(path=destination_dir, members=safemembers(the_tar))
    the_tar.close()
