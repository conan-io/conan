import fnmatch
import os


def _metadata_files(folder, metadata):
    result = {}
    for root, _, files in os.walk(folder):
        for f in files:
            abs_path = os.path.join(root, f)
            relpath = os.path.relpath(abs_path, folder)
            if metadata:
                if not any(fnmatch.fnmatch(relpath, m) for m in metadata):
                    continue
            path = os.path.join("metadata", relpath).replace("\\", "/")
            result[path] = abs_path
    return result


def gather_metadata(upload_data, cache, metadata):
    for rref, recipe_bundle in upload_data.refs():
        if metadata or recipe_bundle["upload"]:
            metadata_folder = cache.ref_layout(rref).metadata()
            assert metadata_folder
            files = _metadata_files(metadata_folder, metadata)
            if files:
                recipe_bundle.setdefault("files", {}).update(files)
                recipe_bundle["upload"] = True

        for pref, pkg_bundle in upload_data.prefs(rref, recipe_bundle):
            if metadata or pkg_bundle["upload"]:
                metadata_folder = cache.pkg_layout(pref).metadata()
                assert metadata_folder
                files = _metadata_files(metadata_folder, metadata)
                if files:
                    pkg_bundle.setdefault("files", {}).update(files)
                    pkg_bundle["upload"] = True
