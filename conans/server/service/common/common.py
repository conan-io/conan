import copy

from conans import DEFAULT_REVISION_V1
from conans.model.package_ref import PkgReference


class CommonService(object):

    def _get_latest_pref(self, pref):
        ref = self._get_latest_ref(pref.ref)
        pref = PkgReference(ref, pref.package_id)
        tmp = self._server_store.get_last_package_revision(pref)
        if not tmp:
            prev = DEFAULT_REVISION_V1
        else:
            prev = tmp.revision
        tmp = copy.copy(pref)
        tmp.revision = prev
        return tmp

    def _get_latest_ref(self, ref):
        tmp = self._server_store.get_last_revision(ref)
        if not tmp:
            rrev = DEFAULT_REVISION_V1
        else:
            rrev = tmp.revision
        return ref.copy_with_rev(rrev)

    def remove_conanfile(self, ref):
        self._authorizer.check_delete_conan(self._auth_user, ref)
        self._server_store.remove_conanfile(ref)

    def remove_packages(self, ref, package_ids_filter):
        """If the revision is not specified it will remove the packages from all the recipes
        (v1 compatibility)"""
        for package_id in package_ids_filter:
            pref = PkgReference(ref, package_id)
            self._authorizer.check_delete_package(self._auth_user, pref)
        if not package_ids_filter:  # Remove all packages, check that we can remove conanfile
            self._authorizer.check_delete_conan(self._auth_user, ref)

        for rrev in self._server_store.get_recipe_revisions(ref):
            self._server_store.remove_packages(ref.copy_with_rev(rrev.revision),
                                               package_ids_filter)

    def remove_package(self, pref):
        self._authorizer.check_delete_package(self._auth_user, pref)

        for rrev in self._server_store.get_recipe_revisions(pref.ref):
            new_ref = pref.ref.copy_with_rev(rrev.revision)
            # FIXME: Just assign rrev when introduce RecipeReference
            new_pref = PkgReference(new_ref, pref.package_id, pref.revision)
            for prev in self._server_store.get_package_revisions(new_pref):
                full_pref = copy.copy(new_pref)
                full_pref.revision = prev.revision
                self._server_store.remove_package(full_pref)

    def remove_all_packages(self, ref):
        for rrev in self._server_store.get_recipe_revisions(ref):
            self._server_store.remove_all_packages(ref.copy_with_rev(rrev.revision))

    def remove_conanfile_files(self, ref, files):
        self._authorizer.check_delete_conan(self._auth_user, ref)
        self._server_store.remove_conanfile_files(ref, files)

    def remove_conanfile_file(self, ref, path):
        self.remove_conanfile_files(ref, [path])
