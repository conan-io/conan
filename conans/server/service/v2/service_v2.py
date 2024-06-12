import copy
import os

from bottle import FileUpload, static_file

from conans.errors import RecipeNotFoundException, PackageNotFoundException, NotFoundException
from conan.internal.paths import CONAN_MANIFEST
from conans.model.package_ref import PkgReference
from conans.server.service.mime import get_mime_type
from conans.server.store.server_store import ServerStore
from conans.util.files import mkdir


class ConanServiceV2:

    def __init__(self, authorizer, server_store):
        assert(isinstance(server_store, ServerStore))
        self._authorizer = authorizer
        self._server_store = server_store

    # RECIPE METHODS
    def get_recipe_file_list(self, ref,  auth_user):
        self._authorizer.check_read_conan(auth_user, ref)
        try:
            file_list = self._server_store.get_recipe_file_list(ref)
        except NotFoundException:
            raise RecipeNotFoundException(ref)
        if not file_list:
            raise RecipeNotFoundException(ref)

        # Send speculative metadata (empty) for files (non breaking future changes)
        return {"files": {key: {} for key in file_list}}

    def get_recipe_file(self, reference, filename, auth_user):
        self._authorizer.check_read_conan(auth_user, reference)
        path = self._server_store.get_recipe_file_path(reference, filename)
        return static_file(os.path.basename(path), root=os.path.dirname(path),
                           mimetype=get_mime_type(path))

    def upload_recipe_file(self, body, headers, reference, filename, auth_user):
        self._authorizer.check_write_conan(auth_user, reference)
        # FIXME: Check that reference contains revision (MANDATORY TO UPLOAD)
        path = self._server_store.get_recipe_file_path(reference, filename)
        self._upload_to_path(body, headers, path)

        # If the upload was ok, of the manifest, update the pointer to the latest
        if filename == CONAN_MANIFEST:
            self._server_store.update_last_revision(reference)

    def get_recipe_revisions_references(self, ref, auth_user):
        self._authorizer.check_read_conan(auth_user, ref)
        ref_norev = copy.copy(ref)
        ref_norev.revision = None
        root = self._server_store.conan_revisions_root(ref_norev)
        if not self._server_store.path_exists(root):
            raise RecipeNotFoundException(ref)
        return self._server_store.get_recipe_revisions_references(ref)

    def get_package_revisions_references(self, pref, auth_user):
        self._authorizer.check_read_conan(auth_user, pref.ref)
        ref_norev = copy.copy(pref.ref)
        ref_norev.revision = None
        root = self._server_store.conan_revisions_root(ref_norev)
        if not self._server_store.path_exists(root):
            raise RecipeNotFoundException(pref.ref)

        ret = self._server_store.get_package_revisions_references(pref)
        return ret

    def get_latest_revision(self, ref, auth_user):
        self._authorizer.check_read_conan(auth_user, ref)
        tmp = self._server_store.get_last_revision(ref)
        if not tmp:
            raise RecipeNotFoundException(ref)
        return tmp

    def get_latest_package_reference(self, pref, auth_user):
        self._authorizer.check_read_conan(auth_user, pref.ref)
        _pref = self._server_store.get_last_package_revision(pref)
        if not _pref:
            raise PackageNotFoundException(pref)
        return _pref

    # PACKAGE METHODS
    def get_package_file_list(self, pref, auth_user):
        self._authorizer.check_read_conan(auth_user, pref.ref)
        file_list = self._server_store.get_package_file_list(pref)
        if not file_list:
            raise PackageNotFoundException(pref)
        # Send speculative metadata (empty) for files (non breaking future changes)
        return {"files": {key: {} for key in file_list}}

    def get_package_file(self, pref, filename, auth_user):
        self._authorizer.check_read_conan(auth_user, pref.ref)
        path = self._server_store.get_package_file_path(pref, filename)
        return static_file(os.path.basename(path), root=os.path.dirname(path),
                           mimetype=get_mime_type(path))

    def upload_package_file(self, body, headers, pref, filename, auth_user):
        self._authorizer.check_write_conan(auth_user, pref.ref)

        # Check if the recipe exists
        recipe_path = self._server_store.export(pref.ref)
        if not os.path.exists(recipe_path):
            raise RecipeNotFoundException(pref.ref)
        path = self._server_store.get_package_file_path(pref, filename)
        self._upload_to_path(body, headers, path)

        # If the upload was ok, of the manifest, update the pointer to the latest
        if filename == CONAN_MANIFEST:
            self._server_store.update_last_package_revision(pref)

    # Misc
    @staticmethod
    def _upload_to_path(body, headers, path):
        file_saver = FileUpload(body, None,
                                filename=os.path.basename(path),
                                headers=headers)
        if os.path.exists(path):
            os.unlink(path)
        if not os.path.exists(os.path.dirname(path)):
            mkdir(os.path.dirname(path))
        file_saver.save(os.path.dirname(path))

    # REMOVE
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
