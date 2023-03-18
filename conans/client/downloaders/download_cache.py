import json
import os

from conan.api.output import ConanOutput
from conans.util.dates import timestamp_now
from conans.util.files import load, save
from conans.util.sha import sha256 as compute_sha256


class DownloadCache:
    def __init__(self, path: str):
        self.path: str = path

    def get_cache_path(self, url, md5, sha1, sha256, conanfile):
        """
        conanfile: if not None, it means it is a call from source() method
        """
        h = sha256  # lets be more efficient for de-dup server files
        if conanfile and not sha256:
            ConanOutput().warning("Expected sha256 to be used as checksum for downloaded sources")
        if h is None:
            h = self._get_hash(url, md5, sha1)
        cached_path = os.path.join(self.path, 's' if conanfile and sha256 else 'c', h)
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
        return os.path.join(self.path, "locks", lock_id)

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
        path_backups = os.path.join(self.path, "s")
        all_refs = {str(k) for k, v in package_list.refs()}
        for f in os.listdir(path_backups):
            if f.endswith(".json"):
                f = os.path.join(path_backups, f)
                content = json.loads(load(f))
                refs = content["references"]
                # TODO: Decide what to do for "unknown" entries. Upload them or leave them?
                if any(ref in all_refs for ref in refs):
                    files_to_upload.append(f)
                    files_to_upload.append(f[:-5])
        return files_to_upload
