import json
import os
from contextlib import contextmanager
from threading import Lock

from conans.util.files import load
from conans.util.locks import SimpleLock


class DownloadCache:
    """ The download cache has 3 folders
    - "s": SOURCE_BACKUP for the files.download(internet_url) backup sources feature
    - "c": CONAN_CACHE: for caching Conan packages artifacts
    - "locks": The LOCKS folder containing the file locks for concurrent access to the cache
    """
    _LOCKS = "locks"

    def __init__(self, path: str):
        self._path: str = path

    _thread_locks = {}  # Needs to be shared among all instances

    @contextmanager
    def lock(self, lock_id):
        lock = os.path.join(self._path, self._LOCKS, lock_id)
        with SimpleLock(lock):
            # Once the process has access, make sure multithread is locked too
            # as SimpleLock doesn't work multithread
            thread_lock = self._thread_locks.setdefault(lock, Lock())
            thread_lock.acquire()
            try:
                yield
            finally:
                thread_lock.release()

    def get_files_to_upload(self, package_list):
        files_to_upload = []
        path_backups = os.path.join(self._path, "s")
        all_refs = {str(k) for k, v in package_list.refs() if v.get("upload")}
        for f in os.listdir(path_backups):
            if f.endswith(".json"):
                f = os.path.join(path_backups, f)
                content = json.loads(load(f))
                refs = content["references"]
                # unknown entries are not uploaded at this moment, the flow is not expected.
                if any(ref in all_refs for ref in refs):
                    files_to_upload.append(f)
                    files_to_upload.append(f[:-5])
        return files_to_upload
