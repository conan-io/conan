import os
from bottle import static_file, FileUpload

from conans.errors import NotFoundException
from conans.server.service.mime import get_mime_type
from conans.server.store.server_store import ServerStore
from conans.server.store.server_store_revisions import ServerStoreRevisions
from conans.util.files import mkdir


class ConanServiceV2(object):

    def __init__(self, authorizer, server_store):
        assert(isinstance(server_store, ServerStore))
        self._authorizer = authorizer
        self._server_store = server_store

    @property
    def with_revisions(self):
        # FIXME: Hard to check if v2 but without revisions
        return isinstance(self._server_store, ServerStoreRevisions)

    # RECIPE METHODS
    def get_recipe_file_list(self, reference,  auth_user):
        self._authorizer.check_read_conan(auth_user, reference)
        file_list = self._server_store.get_recipe_file_list(reference)
        if not file_list:
            raise NotFoundException("conanfile not found")
        if self.with_revisions:
            reference = self._server_store.ref_with_rev(reference)
        else:
            reference = reference.copy_without_revision()

        # Send speculative metadata (empty) for files (non breaking future changes)
        return {"files": {key: {} for key in file_list},
                "reference": reference.full_repr()}

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
        if self.with_revisions:
            self._server_store.update_last_revision(reference)

    # PACKAGE METHODS
    def get_package_file_list(self, p_reference, auth_user):
        self._authorizer.check_read_conan(auth_user, p_reference.conan)
        file_list = self._server_store.get_package_file_list(p_reference)
        if not file_list:
            raise NotFoundException("conanfile not found")
        # Send speculative metadata (empty) for files (non breaking future changes)
        return {"files": {key: {} for key in file_list},
                "reference": p_reference.full_repr()}

    def get_package_file(self, p_reference, filename, auth_user):
        self._authorizer.check_read_conan(auth_user, p_reference.conan)
        path = self._server_store.get_package_file_path(p_reference, filename)
        return static_file(os.path.basename(path), root=os.path.dirname(path),
                           mimetype=get_mime_type(path))

    def upload_package_file(self, body, headers, p_reference, filename, auth_user):
        self._authorizer.check_write_conan(auth_user, p_reference.conan)
        # FIXME: Check that reference contains revisions (MANDATORY TO UPLOAD)

        # Check if the recipe exists
        recipe_path = self._server_store.export(p_reference.conan)
        if not os.path.exists(recipe_path):
            raise NotFoundException("Recipe %s with revision "
                                    "%s doesn't exist in "
                                    "remote" % (str(p_reference.conan),
                                                str(p_reference.conan.revision)))
        path = self._server_store.get_package_file_path(p_reference, filename)
        self._upload_to_path(body, headers, path)

        # If the upload was ok, update the pointer to the latest
        if self.with_revisions:
            self._server_store.update_last_package_revision(p_reference)

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
