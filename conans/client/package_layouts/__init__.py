# coding=utf-8

import os
import platform

from conans.errors import ConanException
from conans.model.ref import ConanFileReference
from conans.client.package_layouts.package_cache_layout import PackageCacheLayout
from conans.client.package_layouts.package_user_layout import PackageUserLayout, LINKED_FOLDER_SENTINEL


def is_case_insensitive_os():
    system = platform.system()
    return system != "Linux" and system != "FreeBSD" and system != "SunOS"


if is_case_insensitive_os():
    def check_ref_case(conan_reference, store_folder):
        if not os.path.exists(store_folder):
            return

        tmp = store_folder
        for part in conan_reference:
            items = os.listdir(tmp)
            try:
                idx = [item.lower() for item in items].index(part.lower())
                if part != items[idx]:
                    raise ConanException("Requested '%s' but found case incompatible '%s'\n"
                                         "Case insensitive filesystem can't manage this"
                                         % (str(conan_reference), items[idx]))
                tmp = os.path.normpath(tmp + os.sep + part)
            except ValueError:
                return
else:
    def check_ref_case(conan_reference, store_folder):  # @UnusedVariable
        pass


def get_package_layout(store_folder, conan_reference, short_paths=False):
    assert isinstance(conan_reference, ConanFileReference)
    base_folder = os.path.normpath(os.path.join(store_folder, "/".join(conan_reference)))

    linked_package_file = os.path.join(base_folder, LINKED_FOLDER_SENTINEL)
    if os.path.exists(linked_package_file):
        return PackageUserLayout(linked_package_file=linked_package_file,
                                 conan_ref=conan_reference, short_paths=short_paths)
    else:
        check_ref_case(conan_reference, store_folder)
        return PackageCacheLayout(base_folder=base_folder,
                                  conan_ref=conan_reference, short_paths=short_paths)
