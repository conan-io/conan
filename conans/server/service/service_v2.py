import os
from bottle import static_file, FileUpload

from conans.errors import NotFoundException
from conans.model.ref import PackageReference
from conans.server.store.server_store import ServerStore
from conans.util.files import mkdir


class RevisionManager(object):

    def __init__(self, revision_enabled, server_store):
        self._revision_enabled = revision_enabled
        self._server_store = server_store

    def patch_ref(self, reference):
        if not self._revision_enabled:
            return reference
        if reference.revision:
            return reference

        latest = self._server_store.get_last_revision(reference)
        if not latest:
            raise NotFoundException("Recipe not found: '%s'" % str(reference))

        reference.revision = latest
        return reference

    def patch_package_ref(self, p_reference):
        if not self._revision_enabled:
            return p_reference
        if p_reference.revision:
            return p_reference

        latest = self._server_store.get_last_package_revision(p_reference)
        if not latest:
            raise NotFoundException("Package not found: '%s'" % str(p_reference))

        reference = self.patch_ref(p_reference.conan)
        ret = PackageReference(reference, p_reference.package_id)
        ret.revision = latest

        return p_reference

    def update_recipe_revision(self, reference):
        if not self._revision_enabled:
            return

        self._server_store.update_last_revision(reference)

    def update_package_revision(self, p_reference):
        if not self._revision_enabled:
            return

        self._server_store.update_last_package_revision(p_reference)


class ConanServiceV2(object):

    def __init__(self, authorizer, server_store, revision_enabled):
        assert(isinstance(server_store, ServerStore))
        self._authorizer = authorizer
        self._server_store = server_store
        self._revision_manager = RevisionManager(revision_enabled, server_store)

    # RECIPE METHODS

    def get_conanfile_files_list(self, reference,  auth_user):
        self._authorizer.check_read_conan(auth_user, reference)
        reference = self._revision_manager.patch_ref(reference)
        snap = self._server_store.get_conanfile_files_list(reference)
        if not snap:
            raise NotFoundException("conanfile not found")
        return {"files": snap, "reference": reference}

    def get_conanfile_file(self, reference, filename, auth_user):
        self._authorizer.check_read_conan(auth_user, reference)
        reference = self._revision_manager.patch_ref(reference)

        path = self._server_store.get_conanfile_file_path(reference, filename)
        mimetype = "x-gzip" if path.endswith(".tgz") else "auto"
        return static_file(os.path.basename(path), root=os.path.dirname(path), mimetype=mimetype)

    def upload_recipe_file(self, body, headers, reference, filename, auth_user):
        self._authorizer.check_write_conan(auth_user, reference)
        reference = self._revision_manager.patch_ref(reference)
        path = self._server_store.get_conanfile_file_path(reference, filename)

        self._upload_to_path(body, headers, path)

        # If the upload was ok, update the pointer to the latest
        self._revision_manager.update_recipe_revision(reference)

    # PACKAGE METHODS

    def get_package_files_list(self, p_reference, auth_user):
        self._authorizer.check_read_conan(auth_user, p_reference.conan)
        p_reference = self._revision_manager.patch_package_ref(p_reference)
        snap = self._server_store.get_package_files_list(p_reference)
        if not snap:
            raise NotFoundException("conanfile not found")
        return {"files": snap, "reference": p_reference}

    def get_package_file(self, p_reference, filename, auth_user):
        self._authorizer.check_read_conan(auth_user, p_reference.conan)
        p_reference = self._revision_manager.patch_package_ref(p_reference)
        path = self._server_store.get_package_file_path(p_reference, filename)
        mimetype = "x-gzip" if path.endswith(".tgz") else "auto"
        return static_file(os.path.basename(path), root=os.path.dirname(path), mimetype=mimetype)

    def upload_package_file(self, body, headers, p_reference, filename, auth_user):
        self._authorizer.check_write_conan(auth_user, p_reference.conan)
        p_reference = self._revision_manager.patch_package_ref(p_reference)

        # Check if the recipe exists
        recipe_path = self._server_store.get_conanfile_path(p_reference.conan)
        if not os.path.exists(recipe_path):
            raise NotFoundException("Recipe %s with revision "
                                    "%s doesn't exist in "
                                    "remote" % (str(p_reference.conan),
                                                str(p_reference.conan.revision)))
        path = self._server_store.get_package_file_path(p_reference, filename)
        self._upload_to_path(body, headers, path)

        # If the upload was ok, update the pointer to the latest
        self._revision_manager.update_package_revision(p_reference)

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
