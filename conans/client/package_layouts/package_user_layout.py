# coding=utf-8

from conans.util.files import load
from conans.client.package_layouts.package_base_layout import PackageBaseLayout


LINKED_FOLDER_SENTINEL = '.linked_package'


class PackageUserLayout(PackageBaseLayout):

    def __init__(self, linked_package_file, conan_ref, short_paths=False):
        base_folder = load(linked_package_file)
        super(PackageUserLayout, self).__init__(base_folder, conan_ref, short_paths)

        # TODO: Parse linked_package_file as may directories won't have the 'standard' layout.
