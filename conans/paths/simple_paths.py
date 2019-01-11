import os

from conans.errors import ConanException
from conans.model.ref import ConanFileReference
from conans.paths import LINKED_PACKAGE_SENTINEL, is_case_insensitive_os
from conans.paths.package_layouts.package_cache_layout import PackageCacheLayout
from conans.paths.package_layouts.package_editable_layout import PackageEditableLayout

if is_case_insensitive_os():
    def check_ref_case(ref, store_folder):
        if not os.path.exists(store_folder):
            return

        tmp = store_folder
        for part in ref.dir_repr().split("/"):
            items = os.listdir(tmp)
            try:
                idx = [item.lower() for item in items].index(part.lower())
                if part != items[idx]:
                    raise ConanException("Requested '%s' but found case incompatible '%s'\n"
                                         "Case insensitive filesystem can't manage this"
                                         % (str(ref), items[idx]))
                tmp = os.path.normpath(tmp + os.sep + part)
            except ValueError:
                return
else:
    def check_ref_case(ref, store_folder):  # @UnusedVariable
        pass


class SimplePaths(object):
    """
    Generate Conan paths. Handles the conan domain path logic. NO DISK ACCESS, just
    path logic responsability
    """
    def __init__(self, store_folder):
        self._store_folder = store_folder

    @property
    def store(self):
        return self._store_folder

    def _build_path_to_base_folder(self, ref):
        return os.path.normpath(os.path.join(self.store, ref.dir_repr()))

    def _build_path_to_linked_folder_sentinel(self, ref):
        base_folder = self._build_path_to_base_folder(ref)
        linked_package_file = os.path.join(base_folder, LINKED_PACKAGE_SENTINEL)
        return linked_package_file

    def package_layout(self, ref, short_paths=False):
        assert isinstance(ref, ConanFileReference), "It is a {}".format(type(ref))
        linked_package_file = self._build_path_to_linked_folder_sentinel(ref)
        if os.path.exists(linked_package_file):
            return PackageEditableLayout(linked_package_file=linked_package_file,
                                         ref=ref)
        else:
            check_ref_case(ref, self.store)
            base_folder = self._build_path_to_base_folder(ref)
            return PackageCacheLayout(base_folder=base_folder,
                                      ref=ref, short_paths=short_paths)

    def conan(self, ref):
        """ the base folder for this package reference, for each ConanFileReference
        """
        return self.package_layout(ref).conan()

    def export(self, ref):
        return self.package_layout(ref).export()

    def export_sources(self, ref, short_paths=False):
        return self.package_layout(ref, short_paths).export_sources()

    def source(self, ref, short_paths=False):
        return self.package_layout(ref, short_paths).source()

    def conanfile(self, ref):
        return self.package_layout(ref).conanfile()

    def builds(self, ref):
        return self.package_layout(ref).builds()

    def build(self, pref, short_paths=False):
        return self.package_layout(pref.ref, short_paths).build(pref)

    def system_reqs(self, ref):
        return self.package_layout(ref).system_reqs()

    def system_reqs_package(self, pref):
        return self.package_layout(pref.ref).system_reqs_package(pref)

    def packages(self, ref):
        return self.package_layout(ref).packages()

    def package(self, pref, short_paths=False):
        return self.package_layout(pref.ref, short_paths).package(pref)

    def scm_folder(self, ref):
        return self.package_layout(ref).scm_folder()

    def package_metadata(self, ref):
        return self.package_layout(ref).package_metadata()

    def installed_as_editable(self, ref):
        return isinstance(self.package_layout(ref), PackageEditableLayout)
