import json
import os

from conan.api.output import ConanOutput
from conans.util.dates import timestamp_now
from conans.util.files import load, save
from conans.util.sha import sha256 as compute_sha256


class DownloadCache:
    """ The download cache has 3 folders
    - "s": SOURCE_BACKUP for the files.download(internet_url) backup sources feature
    - "c": CONAN_CACHE: for caching Conan packages artifacts
    - "locks": The LOCKS folder containing the file locks for concurrent access to the cache
    """
    _SOURCE_BACKUP_DIR = "s"
    _CONAN_CACHE_DIR = "c"
    _LOCKS = "locks"

    def __init__(self, path: str):
        self._path: str = path

    def get_cache_path(self, url, md5, sha1, sha256, conanfile):
        """
        conanfile: if not None, it means it is a call from source() method
        """
        h = sha256  # lets be more efficient for de-dup server files
        if conanfile and not sha256:
            ConanOutput().warning("Expected sha256 to be used as checksum for downloaded sources")
        if h is None:
            h = self._get_hash(url, md5, sha1)
        subfolder = self._SOURCE_BACKUP_DIR if conanfile and sha256 else self._CONAN_CACHE_DIR
        cached_path = os.path.join(self._path, subfolder, h)
        return cached_path, h

    @staticmethod
    def update_backup_sources_json(cached_path, conanfile, url):
        summary_path = cached_path + ".json"
        if os.path.exists(summary_path):
            summary = json.loads(load(summary_path))
        else:
            summary = {"references": {}, "timestamp": timestamp_now()}

        try:
            summary_key = str(conanfile.ref)
        except AttributeError:
            # The recipe path would be different between machines
            # So best we can do is to set this as unknown
            summary_key = "unknown"

        urls = summary["references"].setdefault(summary_key, [])
        if url not in urls:
            urls.append(url)
        save(summary_path, json.dumps(summary))

    def get_lock_path(self, lock_id):
        return os.path.join(self._path, self._LOCKS, lock_id)

    @staticmethod
    def _get_hash(url, md5, sha1):
        """ For Api V2, the cached downloads always have recipe and package REVISIONS in the URL,
        making them immutable, and perfect for cached downloads of artifacts. For V2 checksum
        will always be None.
        """
        checksum = sha1 or md5
        if checksum is not None:
            url += checksum
        h = compute_sha256(url.encode())
        return h

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
