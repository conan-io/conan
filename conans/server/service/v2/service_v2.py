import os

from bottle import FileUpload, static_file

from conans.errors import NotFoundException
from conans.server.service.common.common import CommonService
from conans.server.service.mime import get_mime_type
from conans.server.store.server_store import ServerStore
from conans.util.files import mkdir


class ConanServiceV2(CommonService):

    def __init__(self, authorizer, server_store):
        assert(isinstance(server_store, ServerStore))
        self._authorizer = authorizer
        self._server_store = server_store

    # RECIPE METHODS
    def get_recipe_file_list(self, reference,  auth_user):
        self._authorizer.check_read_conan(auth_user, reference)
        the_time = self._server_store.get_revision_time(reference)
        file_list = self._server_store.get_recipe_file_list(reference)
        if not file_list:
            raise NotFoundException("conanfile not found")

        # Send speculative metadata (empty) for files (non breaking future changes)
        return {"files": {key: {} for key in file_list},
                "reference": reference.full_repr(),
                "time": the_time}

    def get_conanfile_file(self, reference, filename, auth_user):
        self._authorizer.check_read_conan(auth_user, reference)
        path = self._server_store.get_conanfile_file_path(reference, filename)
        return static_file(os.path.basename(path), root=os.path.dirname(path),
                           mimetype=get_mime_type(path))

    def upload_recipe_file(self, body, headers, reference, filename, auth_user):
        self._authorizer.check_write_conan(auth_user, reference)
        # FIXME: Check that reference contains revision (MANDATORY TO UPLOAD)
        path = self._server_store.get_conanfile_file_path(reference, filename)
        self._upload_to_path(body, headers, path)

        # If the upload was ok, update the pointer to the latest
        self._server_store.update_last_revision(reference)

    def get_recipe_revisions(self, ref, auth_user):
        self._authorizer.check_read_conan(auth_user, ref)
        root = self._server_store.conan_revisions_root(ref.copy_clear_rev())
        if not self._server_store.path_exists(root):
            raise NotFoundException("Recipe not found: '%s'" % str(ref))
        return self._server_store.get_recipe_revisions(ref)

    def get_package_revisions(self, pref, auth_user):
        self._authorizer.check_read_conan(auth_user, pref.ref)
        root = self._server_store.conan_revisions_root(pref.ref.copy_clear_rev())
        if not self._server_store.path_exists(root):
            raise NotFoundException("Recipe not found: '%s'" % pref.ref.full_repr())
        # Will raise if no package is there
        self._server_store.package(pref)
        ret = self._server_store.get_package_revisions(pref)
        return ret

    # PACKAGE METHODS
    def get_package_file_list(self, pref, auth_user):
        self._authorizer.check_read_conan(auth_user, pref.ref)
        file_list = self._server_store.get_package_file_list(pref)
        if not file_list:
            raise NotFoundException("conanfile not found")

        the_time = self._server_store.get_package_revision_time(pref)
        # Send speculative metadata (empty) for files (non breaking future changes)
        return {"files": {key: {} for key in file_list},
                "reference": pref.full_repr(),
                "time": the_time}

    def get_package_file(self, pref, filename, auth_user):
        self._authorizer.check_read_conan(auth_user, pref.ref)
        path = self._server_store.get_package_file_path(pref, filename)
        return static_file(os.path.basename(path), root=os.path.dirname(path),
                           mimetype=get_mime_type(path))

    def upload_package_file(self, body, headers, pref, filename, auth_user):
        self._authorizer.check_write_conan(auth_user, pref.ref)
        # FIXME: Check that reference contains revisions (MANDATORY TO UPLOAD)

        # Check if the recipe exists
        recipe_path = self._server_store.export(pref.ref)
        if not os.path.exists(recipe_path):
            raise NotFoundException("Recipe %s with revision %s doesn't exist in "
                                    "remote" % (str(pref.ref), str(pref.ref.revision)))
        path = self._server_store.get_package_file_path(pref, filename)
        self._upload_to_path(body, headers, path)

        # If the upload was ok, update the pointer to the latest
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
