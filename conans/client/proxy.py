import os

from requests.exceptions import RequestException

from conans.client.output import ScopedOutput
from conans.client.remover import DiskRemover
from conans.client.recorder.action_recorder import INSTALL_ERROR_MISSING, INSTALL_ERROR_NETWORK
from conans.errors import (ConanException, NotFoundException, NoRemoteAvailable)
from conans.util.log import logger
from conans.util.tracer import log_recipe_got_from_local_cache
from conans.model.manifest import FileTreeManifest


class ConanProxy(object):
    """ Class to access the conan storage, to perform typical tasks as to get packages,
    getting conanfiles, uploading, removing from remote, etc.
    It uses the registry to control where the packages come from.
    """
    def __init__(self, client_cache, user_io, remote_manager, remote_name, recorder, registry):
        # collaborators
        self._client_cache = client_cache
        self._out = user_io.out
        self._remote_manager = remote_manager
        self._registry = registry
        self._recorder = recorder
        # inputs
        self._remote_name = remote_name

    @property
    def registry(self):
        return self._registry

    def get_recipe(self, conan_reference, check_updates, update):
        with self._client_cache.conanfile_write_lock(conan_reference):
            result = self._get_recipe(conan_reference, check_updates, update)
        return result

    def _get_recipe(self, conan_reference, check_updates, update):
        output = ScopedOutput(str(conan_reference), self._out)
        check_updates = check_updates or update
        # check if it is in disk
        conanfile_path = self._client_cache.conanfile(conan_reference)

        status = None
        if os.path.exists(conanfile_path):
            if check_updates:
                ret = self._update_available(conan_reference)
                if ret != 0:  # Found and not equal
                    remote, _ = self._get_remote(conan_reference)
                    if ret == 1:
                        if not update:
                            status = "AVAILABLE"
                        else:
                            DiskRemover(self._client_cache).remove(conan_reference)
                            output.info("Retrieving from remote '%s'..." % remote.name)
                            self._remote_manager.get_recipe(conan_reference, remote)
                            status = "UPDATED"
                    elif ret == -1:
                        status = "NEWER_NO_UPDATED" if update else "NEWER"

            log_recipe_got_from_local_cache(conan_reference)
            self._recorder.recipe_fetched_from_cache(conan_reference)
        else:
            self._retrieve_recipe(conan_reference, output)

        return conanfile_path, status

    def _update_available(self, conan_reference):
        """Returns 0 if the conanfiles are equal, 1 if there is an update and -1 if
        the local is newer than the remote"""
        if not conan_reference:
            return 0
        export = self._client_cache.export(conan_reference)
        if os.path.exists(export):
            read_manifest = FileTreeManifest.load(export)
            try:  # get_conan_manifest can fail, not in server
                remote, _ = self._get_remote(conan_reference)
                upstream_manifest = self._remote_manager.get_conan_manifest(conan_reference, remote)
                if upstream_manifest != read_manifest:
                    return 1 if upstream_manifest.time > read_manifest.time else -1
            except (NotFoundException, NoRemoteAvailable):  # 404
                pass

        return 0

    def _retrieve_recipe(self, conan_reference, output):
        """ returns the requested conanfile object, retrieving it from
        remotes if necessary. Can raise NotFoundException
        """
        def _retrieve_from_remote(the_remote):
            output.info("Trying with '%s'..." % the_remote.name)
            self._remote_manager.get_recipe(conan_reference, the_remote)
            self._registry.set_ref(conan_reference, the_remote)
            self._recorder.recipe_downloaded(conan_reference, the_remote.url)

        if self._remote_name:
            output.info("Not found, retrieving from server '%s' " % self._remote_name)
            ref_remote = self._registry.remote(self._remote_name)
        else:
            ref_remote = self._registry.get_ref(conan_reference)
            if ref_remote:
                output.info("Retrieving from predefined remote '%s'" % ref_remote.name)

        if ref_remote:
            try:
                _retrieve_from_remote(ref_remote)
                return
            except NotFoundException:
                msg = "%s was not found in remote '%s'" % (str(conan_reference), ref_remote.name)
                self._recorder.recipe_install_error(conan_reference, INSTALL_ERROR_MISSING,
                                                    msg, ref_remote.url)
                raise NotFoundException(msg)
            except RequestException as exc:
                self._recorder.recipe_install_error(conan_reference, INSTALL_ERROR_NETWORK,
                                                    str(exc), ref_remote.url)
                raise exc

        output.info("Not found in local cache, looking in remotes...")
        remotes = self._registry.remotes
        if not remotes:
            raise ConanException("No remote defined")
        for remote in remotes:
            logger.debug("Trying with remote %s" % remote.name)
            try:
                _retrieve_from_remote(remote)
                return
            # If not found continue with the next, else raise
            except NotFoundException as exc:
                pass
        else:
            msg = "Unable to find '%s' in remotes" % str(conan_reference)
            logger.debug("Not found in any remote")
            self._recorder.recipe_install_error(conan_reference, INSTALL_ERROR_MISSING,
                                                msg, None)
            raise NotFoundException(msg)

    def _get_remote(self, conan_ref=None):
        # Prioritize -r , then reference registry and then the default remote
        ref_remote = self._registry.get_ref(conan_ref) if conan_ref else None
        if self._remote_name:
            remote = self._registry.remote(self._remote_name)
        else:
            remote = ref_remote or self._registry.default_remote
        return remote, ref_remote

    def search_remotes(self, pattern=None, ignorecase=True):
        if self._remote_name:
            remote = self._registry.remote(self._remote_name)
            search_result = self._remote_manager.search_recipes(remote, pattern, ignorecase)
            return search_result

        for remote in self._registry.remotes:
            search_result = self._remote_manager.search_recipes(remote, pattern, ignorecase)
            if search_result:
                return search_result
