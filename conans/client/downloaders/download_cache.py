import json
import os

from conan.api.output import ConanOutput
from conans.util.files import load, save
from conans.util.sha import sha256 as compute_sha256


class DownloadCache:
    def __init__(self, path: str):
        self.path: str = path

    def get_cache_path(self, url, md5, sha1, sha256, conanfile):
        """
        conanfile: if not None, it means it is a call from source() method
        """
        sources_cache = False
        h = None
        if conanfile is not None:
            if sha256:
                h = sha256
                sources_cache = True
            else:
                ConanOutput() \
                    .warning("Expected sha256 to be used as file checksums for downloaded sources")
        if h is None:
            h = self._get_hash(url, md5, sha1, sha256)
        cached_path = os.path.join(self.path, 's' if sources_cache else 'c', h)
        return cached_path, h

    @staticmethod
    def update_backup_sources_json(cached_path, conanfile, url):
        summary_path = cached_path + ".json"
        summary = json.loads(load(summary_path)) if os.path.exists(summary_path) else {}

        try:
            summary_key = conanfile.ref.repr_notime()
        except AttributeError:
            # The recipe path would be different between machines
            # So best we can do is to set this as unknown
            summary_key = "unknown"

        urls = summary.setdefault(summary_key, [])
        if url not in urls:
            urls.append(url)
        save(summary_path, json.dumps(summary))

    def get_lock_path(self, lock_id):
        return os.path.join(self.path, "locks", lock_id)

    @staticmethod
    def _get_hash(url, md5, sha1, sha256):
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
        path_backups = os.path.join(self.path, "s")
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
