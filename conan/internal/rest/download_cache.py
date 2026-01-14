import hashlib
import json
import os
from contextlib import contextmanager

from conan.errors import ConanException
from conan.internal.cache.concurrency_lock import ConcurrencyLock
from conan.internal.util.dates import timestamp_now
from conan.internal.util.files import load, save, remove_if_dirty


class DownloadCache:
    """ The download cache has 3 folders
    - "s": SOURCE_BACKUP for the files.download(internet_url) backup sources feature
    - "c": CONAN_CACHE: for caching Conan packages artifacts
    - "locks": The LOCKS folder containing the file locks for concurrent access to the cache
    """
    _LOCKS = "locks"
    _SOURCE_BACKUP = "s"
    _CONAN_CACHE = "c"

    def __init__(self, path: str):
        self._path: str = path
        self._lock_manager = ConcurrencyLock(path)

    def source_path(self, sha256):
        return os.path.join(self._path, self._SOURCE_BACKUP, sha256)

    def cached_path(self, url):
        md = hashlib.sha256()
        md.update(url.encode())
        h = md.hexdigest()
        return os.path.join(self._path, self._CONAN_CACHE, h), h

    @contextmanager
    def lock(self, lock_id):
        """
        Acquire an exclusive lock for download cache operations.

        Uses ConcurrencyLock for inter-process and thread-safe locking.
        Lock level is None (no hierarchy enforcement) since download cache
        operations are independent and don't interact with recipe/package locks.
        """
        with self._lock_manager.lock(lock_id, level=None):
            yield

    def get_backup_sources_files(self, excluded_urls, package_list=None, only_upload=True):
        """Get list of backup source files currently present in the cache,
        either all of them if no package_list is give, or filtered by those belonging to the references in the package_list

        Will exclude the sources that come from URLs present in excluded_urls

        @param excluded_urls: a list of URLs to exclude backup sources files if they come from any of these URLs
        @param package_list: a PackagesList object to filter backup files from (The files should have been downloaded form any of the references in the package_list)
        @param only_upload: if True, only return the files for packages that are set to be uploaded"""
        path_backups = os.path.join(self._path, self._SOURCE_BACKUP)

        if not os.path.exists(path_backups):
            return []

        if excluded_urls is None:
            excluded_urls = []

        def has_excluded_urls(backup_urls):
            return all(any(url.startswith(excluded_url)
                           for excluded_url in excluded_urls)
                       for url in backup_urls)

        all_refs = set()
        if package_list is not None:
            for ref, packages in package_list.items():
                ref_info = package_list.recipe_dict(ref)
                if (not only_upload or ref_info.get("upload")
                        or any(package_list.package_dict(p).get("upload") for p in packages)):
                    all_refs.add(str(ref))

        path_backups_contents = []

        dirty_ext = ".dirty"
        for path in os.listdir(path_backups):
            if remove_if_dirty(os.path.join(path_backups, path)):
                continue
            if path.endswith(dirty_ext):
                if not os.path.exists(os.path.join(path_backups, os.path.splitext(path)[0])):
                    if os.path.exists(os.path.join(path_backups, path)):
                        os.remove(os.path.join(path_backups, path))
                continue
            if not path.endswith(".json"):
                path_backups_contents.append(path)

        files_to_upload = []

        for path in path_backups_contents:
            blob_path = os.path.join(path_backups, path)
            metadata_path = os.path.join(blob_path + ".json")
            if not os.path.exists(metadata_path):
                raise ConanException(f"Missing metadata file for backup source {blob_path}")
            metadata = json.loads(load(metadata_path))
            refs = metadata["references"]
            for ref, urls in refs.items():
                if not has_excluded_urls(urls) and (not only_upload
                                                    or package_list is None
                                                    or ref in all_refs):
                    files_to_upload.append(metadata_path)
                    files_to_upload.append(blob_path)
                    break
        return files_to_upload

    def update_backup_sources_json(self, cached_path, conanfile, urls):
        """Update backup sources JSON with concurrency protection and atomic write.

        Creates or updates the sha256.json file with the references and new urls used.
        Uses locking to prevent race conditions when multiple processes download the
        same source file concurrently.
        """
        summary_path = cached_path + ".json"

        # Extract lock ID from cached_path (the sha256 hash)
        lock_id = os.path.basename(cached_path)

        # Protect read-modify-write with lock
        with self._lock_manager.lock(lock_id):
            # Read existing metadata or create new
            if os.path.exists(summary_path):
                summary = json.loads(load(summary_path))
            else:
                summary = {"references": {}, "timestamp": timestamp_now()}

            # Determine the summary key (package reference)
            try:
                summary_key = str(conanfile.ref)
            except AttributeError:
                # If there's no node associated with the conanfile,
                # try to construct a reference from the conanfile itself.
                # We accept it if we have a name and a version at least.
                if conanfile.name and conanfile.version:
                    user = f"@{conanfile.user}" if conanfile.user else ""
                    channel = f"/{conanfile.channel}" if conanfile.channel else ""
                    summary_key = f"{conanfile.name}/{conanfile.version}{user}{channel}"
                else:
                    # The recipe path would be different between machines
                    # So best we can do is to set this as unknown
                    summary_key = "unknown"

            # Modify: add new URLs if not already present
            if not isinstance(urls, (list, tuple)):
                urls = [urls]
            existing_urls = summary["references"].setdefault(summary_key, [])
            existing_urls.extend(url for url in urls if url not in existing_urls)

            conanfile.output.verbose(f"Updating ${summary_path} summary file")
            summary_dump = json.dumps(summary)
            conanfile.output.debug(f"New summary: ${summary_dump}")

            # Write atomically: temp file + os.replace()
            # This ensures that if interrupted, the original file is unchanged
            tmp_path = summary_path + ".tmp"
            save(tmp_path, json.dumps(summary))
            os.replace(tmp_path, summary_path)
