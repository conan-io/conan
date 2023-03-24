import os


def _metadata_files(folder, upload_files):
    for root, _, files in os.walk(folder):
        for f in files:
            abs_path = os.path.join(root, f)
            relpath = os.path.relpath(abs_path, folder)
            path = os.path.join("metadata", relpath).replace("\\", "/")
            upload_files[path] = abs_path


def gather_metadata(upload_data, cache):
    for rref, recipe_bundle in upload_data.refs():
        if recipe_bundle["upload"]:
            metadata_folder = cache.ref_layout(rref).metadata()
            assert metadata_folder
            _metadata_files(metadata_folder, recipe_bundle["files"])
        for pref, pkg_bundle in upload_data.prefs(rref, recipe_bundle):
            if pkg_bundle["upload"]:
                metadata_folder = cache.pkg_layout(pref).metadata()
                assert metadata_folder
                _metadata_files(metadata_folder, pkg_bundle["files"])
