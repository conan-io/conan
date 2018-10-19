# coding=utf-8

import os

from conans.model.ref import ConanFileReference
from conans.client.package_layouts.package_cache_layout import PackageCacheLayout
from conans.client.package_layouts.package_user_layout import PackageUserLayout, LINKED_FOLDER_SENTINEL


def get_package_layout(store_folder, conan_reference, short_paths=False):
    assert isinstance(conan_reference, ConanFileReference)
    base_folder = os.path.normpath(os.path.join(store_folder, "/".join(conan_reference)))

    linked_package_file = os.path.join(base_folder, LINKED_FOLDER_SENTINEL)
    if os.path.exists(linked_package_file):
        return PackageUserLayout(linked_package_file,
                                 conan_ref=conan_reference, short_paths=short_paths)
    else:
        return PackageCacheLayout(base_folder=base_folder,
                                  conan_ref=conan_reference, short_paths=short_paths)
