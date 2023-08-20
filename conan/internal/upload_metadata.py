import fnmatch
import os

from conan.api.output import ConanOutput


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


def gather_metadata(package_list, cache, metadata):
    for rref, recipe_bundle in package_list.refs().items():
        if metadata or recipe_bundle["upload"]:
            metadata_folder = cache.recipe_layout(rref).metadata()
            files = _metadata_files(metadata_folder, metadata)
            if files:
                ConanOutput(scope=str(rref)).info(f"Recipe metadata: {len(files)} files")
                recipe_bundle.setdefault("files", {}).update(files)
                recipe_bundle["upload"] = True

        for pref, pkg_bundle in package_list.prefs(rref, recipe_bundle).items():
            if metadata or pkg_bundle["upload"]:
                metadata_folder = cache.pkg_layout(pref).metadata()
                files = _metadata_files(metadata_folder, metadata)
                if files:
                    ConanOutput(scope=str(pref)).info(f"Package metadata: {len(files)} files")
                    pkg_bundle.setdefault("files", {}).update(files)
                    pkg_bundle["upload"] = True
