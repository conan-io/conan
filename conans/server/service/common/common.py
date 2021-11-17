import copy

from conans.model.package_ref import PkgReference


class CommonService(object):

    def remove_recipe(self, ref, auth_user):
        self._authorizer.check_delete_conan(auth_user, ref)
        self._server_store.remove_recipe(ref)

    def remove_package(self, pref, auth_user):
        self._authorizer.check_delete_package(auth_user, pref)

        for rrev in self._server_store.get_recipe_revisions_references(pref.ref):
            new_ref = copy.copy(pref.ref)
            new_ref.revision = rrev.revision
            # FIXME: Just assign rrev when introduce RecipeReference
            new_pref = PkgReference(new_ref, pref.package_id, pref.revision)
            for _pref in self._server_store.get_package_revisions_references(new_pref):
                self._server_store.remove_package(_pref)

    def remove_all_packages(self, ref, auth_user):
        self._authorizer.check_delete_conan(auth_user, ref)
        for rrev in self._server_store.get_recipe_revisions_references(ref):
            tmp = copy.copy(ref)
            tmp.revision = rrev.revision
            self._server_store.remove_all_packages(tmp)

    def remove_recipe_files(self, ref, files):
        self._authorizer.check_delete_conan(self._auth_user, ref)
        self._server_store.remove_recipe_files(ref, files)

    def remove_recipe_file(self, ref, path):
        self.remove_recipe_files(ref, [path])
