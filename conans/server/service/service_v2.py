import os
from bottle import static_file, FileUpload

from conans.errors import NotFoundException
from conans.server.store.server_store import ServerStore
from conans.util.files import mkdir


class RevisionManager(object):

    def __init__(self, revision_enabled, server_store):
        self._revision_enabled = revision_enabled
        self._server_store = server_store

    def get_revision(self, reference, header):
        if not self._revision_enabled:
            return ""
        revision = header or self._server_store.get_last_revision(reference)
        if not revision:
            raise NotFoundException("'%s' not found" % str(reference))
        return revision

    def update_revision(self, reference, revision):
        if not self._revision_enabled:
            return
        self._server_store.update_last_revision(reference, revision)


class ConanServiceV2(object):

    def __init__(self, authorizer, server_store, revision_enabled):
        assert(isinstance(server_store, ServerStore))
        self._authorizer = authorizer
        self._server_store = server_store
        self._revision_manager = RevisionManager(revision_enabled, server_store)

    # RECIPE METHODS

    def get_conanfile_files_list(self, reference, revision_header, auth_user):
        self._authorizer.check_read_conan(auth_user, reference)
        revision = self._revision_manager.get_revision(reference, revision_header)
        snap = self._server_store.get_conanfile_files_list(reference, revision)
        if not snap:
            raise NotFoundException("conanfile not found")
        return {"files": snap, "revision": revision}

    def get_conanfile_file(self, reference, filename, revision_header, auth_user):
        self._authorizer.check_read_conan(auth_user, reference)
        revision = self._revision_manager.get_revision(reference, revision_header)

        path = self._server_store.get_conanfile_file_path(reference, filename, revision)
        mimetype = "x-gzip" if path.endswith(".tgz") else "auto"
        return static_file(os.path.basename(path), root=os.path.dirname(path), mimetype=mimetype)

    def upload_recipe_file(self, body, headers, reference, filename, revision_header, auth_user):
        self._authorizer.check_write_conan(auth_user, reference)
        revision = self._revision_manager.get_revision(reference, revision_header)
        path = self._server_store.get_conanfile_file_path(reference, filename, revision)
        if not os.path.exists(path):
            self._server_store.update_last_revision(reference, revision)
        self._upload_to_path(body, headers, path)

    # PACKAGE METHODS

    def get_package_files_list(self, p_reference, revision_header, auth_user):
        self._authorizer.check_read_conan(auth_user, p_reference.conan)
        revision = self._revision_manager.get_revision(p_reference.conan, revision_header)
        snap = self._server_store.get_package_files_list(p_reference, revision)
        if not snap:
            raise NotFoundException("conanfile not found")
        return {"files": snap, "revision": revision}

    def get_package_file(self, p_reference, filename, revision_header, auth_user):
        self._authorizer.check_read_conan(auth_user, p_reference.conan)
        revision = self._revision_manager.get_revision(p_reference.conan, revision_header)
        path = self._server_store.get_package_file_path(p_reference, filename, revision)
        mimetype = "x-gzip" if path.endswith(".tgz") else "auto"
        return static_file(os.path.basename(path), root=os.path.dirname(path), mimetype=mimetype)

    def upload_package_file(self, body, headers, p_reference, filename, revision_header, auth_user):
        self._authorizer.check_write_conan(auth_user, p_reference.conan)
        revision = self._revision_manager.get_revision(p_reference.conan, revision_header)
        path = self._server_store.get_package_file_path(p_reference, filename, revision)
        self._upload_to_path(body, headers, path)

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
