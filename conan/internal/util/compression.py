from functools import lru_cache
from conan.internal.cache.home_paths import HomePaths
from conan.internal.loader import load_python_file
from conan.internal.errors import ConanException

import os
import gzip
import time
import tarfile
from conan.api.output import ConanOutput
from conan.internal.util.files import set_dirty_context_manager

def tar_extract(src_path, destination_dir, compression_plugin=None):
    if compression_plugin:
       return compression_plugin.tar_extract(src_path, destination_dir)

    with open(src_path, mode='rb') as file_handler:
        the_tar = tarfile.open(fileobj=file_handler)
        # NOTE: The errorlevel=2 has been removed because it was failing in Win10, it didn't allow to
        # "could not change modification time", with time=0
        # the_tar.errorlevel = 2  # raise exception if any error
        the_tar.extraction_filter = (lambda member, path: member)  # fully_trusted, avoid Py3.14 break
        the_tar.extractall(path=destination_dir)
        the_tar.close()


def tar_compress(files, name, dest_dir, compresslevel=None, ref=None, recursive=False, compression_plugin=None):
    if compression_plugin:
        return compression_plugin.tar_compress(files, name, dest_dir, compresslevel, ref)

    t1 = time.time()
    # FIXME, better write to disk sequentially and not keep tgz contents in memory
    tgz_path = os.path.join(dest_dir, name)
    ConanOutput(scope=str(ref) if ref else "").info(f"Compressing {name}")
    with set_dirty_context_manager(tgz_path), open(tgz_path, "wb") as tgz_handle:
        tgz = gzopen_without_timestamps(name, fileobj=tgz_handle, compresslevel=compresslevel)
        for filename, abs_path in sorted(files.items()):
            # recursive is False in case it is a symlink to a folder
            tgz.add(abs_path, filename, recursive=recursive)
        tgz.close()

    duration = time.time() - t1
    ConanOutput().debug(f"{name} compressed in {duration} time")
    return tgz_path

def gzopen_without_timestamps(name, fileobj, compresslevel=None):
    """ !! Method overrided by laso to pass mtime=0 (!=None) to avoid time.time() was
        setted in Gzip file causing md5 to change. Not possible using the
        previous tarfile open because arguments are not passed to GzipFile constructor
    """
    compresslevel = compresslevel if compresslevel is not None else 9  # default Gzip = 9
    fileobj = gzip.GzipFile(name, "w", compresslevel, fileobj, mtime=0)
    # Format is forced because in Python3.8, it changed and it generates different tarfiles
    # with different checksums, which break hashes of tgzs
    # PAX_FORMAT is the default for Py38, lets make it explicit for older Python versions
    t = tarfile.TarFile.taropen(name, "w", fileobj, format=tarfile.PAX_FORMAT)
    t._extfileobj = False
    return t


def load_compression_plugin(cache_folder):
    if not cache_folder:
        return None
    compression_plugin_path = HomePaths(cache_folder).compression_plugin_path
    if not os.path.exists(compression_plugin_path):
        return None

    mod, _ = load_python_file(compression_plugin_path)
    if not hasattr(mod, "tar_extract") or not hasattr(mod, "tar_compress"):
        raise ConanException("The 'compression.py' plugin does not contain required `tar_extract` or `tar_compress` functions")
    return mod


"""
Plugin `compression.py` interface:

    def tar_extract(src_path: str, destination_dir: str) -> None
    def tar_compress(files: List[str], name: str, dest_dir: str, compresslevel=None, ref: str=None, cache_folder:str, recursive: bool = False) -> str
"""
