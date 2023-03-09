import json
import os

from conans.util.files import load
from conans.util.sha import sha256 as compute_sha256


class DownloadCache:
    def __init__(self, path: str):
        self.path: str = path

    def get_lock_path(self, lock_id):
        return os.path.join(self.path, "locks", lock_id)

    def get_local_sources_cache_path(self):
        return os.path.join(self.path, 's')

    def get_local_conan_cache_path(self):
        return os.path.join(self.path, 'c')

    @staticmethod
    def get_hash(url, md5, sha1, sha256):
        """ For Api V2, the cached downloads always have recipe and package REVISIONS in the URL,
        making them immutable, and perfect for cached downloads of artifacts. For V2 checksum
        will always be None.
        """
        checksum = sha256 or sha1 or md5
        if checksum is not None:
            url += checksum
        h = compute_sha256(url.encode())
        return h

    def get_files_to_upload(self, package_list):
        files_to_upload = []
        path_backups = self.get_local_sources_cache_path()
        all_refs = {k.repr_notime() for k, v in package_list.refs()}
        for f in os.listdir(path_backups):
            if f.endswith(".json"):
                f = os.path.join(path_backups, f)
                refs = json.loads(load(f))
                # TODO: Decide what to do for "unknown" entries. Upload them or leave them?
                if any(ref in all_refs for ref in refs):
                    files_to_upload.append(f)
                    files_to_upload.append(f[:-5])
        return files_to_upload
