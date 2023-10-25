import fnmatch
import os

from conan.api.output import ConanOutput
from conan.errors import ConanException


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


def gather_metadata(package_list, cache, metadata: list):
    """
    List and configure the metadata files to be uploaded.
    The metadata supports patterns, so it can be used to upload only a subset of the metadata files.
    When metadata is not specified, all metadata files are uploaded.

    :param package_list: Package to be uploaded
    :param cache: Conan client cache
    :param metadata: A list of patterns of metadata that should be uploaded. Default None
    """
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
