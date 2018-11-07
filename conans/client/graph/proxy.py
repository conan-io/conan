import os

from requests.exceptions import RequestException

from conans.client.graph.graph import (RECIPE_DOWNLOADED, RECIPE_INCACHE,
                                       RECIPE_UPDATED, RECIPE_NEWER, RECIPE_UPDATEABLE,
                                       RECIPE_NO_REMOTE, RECIPE_NOT_IN_REMOTE)
from conans.client.output import ScopedOutput
from conans.client.recorder.action_recorder import INSTALL_ERROR_MISSING, INSTALL_ERROR_NETWORK
from conans.client.remover import DiskRemover
from conans.errors import ConanException, NotFoundException
from conans.model.manifest import FileTreeManifest
from conans.util.env_reader import get_env
from conans.util.log import logger
from conans.util.tracer import log_recipe_got_from_local_cache


class ConanProxy(object):
    def __init__(self, client_cache, output, remote_manager, registry):
        # collaborators
        self._client_cache = client_cache
        self._out = output
        self._remote_manager = remote_manager
        self._registry = registry

    def get_recipe(self, conan_reference, check_updates, update, remote_name, recorder):
        with self._client_cache.conanfile_write_lock(conan_reference):
            result = self._get_recipe(conan_reference, check_updates, update, remote_name, recorder)
            conanfile_path, status, remote, reference = result

            if status not in (RECIPE_DOWNLOADED, RECIPE_UPDATED):
                log_recipe_got_from_local_cache(reference)
                recorder.recipe_fetched_from_cache(reference)

        return conanfile_path, status, remote, reference

    def _get_recipe(self, reference, check_updates, update, remote_name, recorder):
        output = ScopedOutput(str(reference), self._out)
        # check if it is in disk
        conanfile_path = self._client_cache.conanfile(reference)

        # NOT in disk, must be retrieved from remotes
        if not os.path.exists(conanfile_path):
            remote, new_ref = self._download_recipe(reference, output, remote_name, recorder)
            status = RECIPE_DOWNLOADED
            return conanfile_path, status, remote, new_ref

        metadata = self._client_cache.load_metadata(reference)
        cur_revision = metadata.recipe.revision
        remote = self._registry.refs.get(reference)
        named_remote = self._registry.remotes.get(remote_name) if remote_name else None
        update_remote = named_remote or remote

        # Check if we have a revision different from the requested one
        revisions_enabled = get_env("CONAN_CLIENT_REVISIONS_ENABLED", False)
        if revisions_enabled and reference.revision and cur_revision != reference.revision:
            output.info("Different revision requested, removing current local recipe...")
            DiskRemover(self._client_cache).remove_recipe(reference)

            output.info("Retrieving from remote '%s'..." % update_remote.name)
            new_ref = self._remote_manager.get_recipe(reference, update_remote)
            self._registry.refs.set(new_ref, update_remote.name)
            status = RECIPE_UPDATED
            return conanfile_path, status, update_remote, new_ref

        check_updates = check_updates or update
        # Recipe exists in disk, but no need to check updates
        if not check_updates:
            status = RECIPE_INCACHE
            ref = reference.copy_with_rev(cur_revision)
            return conanfile_path, status, remote, ref

        if not update_remote:
            status = RECIPE_NO_REMOTE
            ref = reference.copy_with_rev(cur_revision)
            return conanfile_path, status, None, ref

        try:  # get_conan_manifest can fail, not in server
            upstream_manifest = self._remote_manager.get_conan_manifest(reference, update_remote)
        except NotFoundException:
            status = RECIPE_NOT_IN_REMOTE
            ref = reference.copy_with_rev(cur_revision)
            return conanfile_path, status, update_remote, ref

        export = self._client_cache.export(reference)
        read_manifest = FileTreeManifest.load(export)
        if upstream_manifest != read_manifest:
            if upstream_manifest.time > read_manifest.time:
                if update:
                    DiskRemover(self._client_cache).remove_recipe(reference)
                    output.info("Retrieving from remote '%s'..." % update_remote.name)
                    new_ref = self._remote_manager.get_recipe(reference, update_remote)
                    self._registry.refs.set(new_ref, update_remote.name)
                    status = RECIPE_UPDATED
                    return conanfile_path, status, update_remote, new_ref
                else:
                    status = RECIPE_UPDATEABLE
            else:
                status = RECIPE_NEWER
        else:
            status = RECIPE_INCACHE

        ref = reference.copy_with_rev(cur_revision)
        return conanfile_path, status, update_remote, ref

    def _download_recipe(self, conan_reference, output, remote_name, recorder):
        def _retrieve_from_remote(the_remote):
            output.info("Trying with '%s'..." % the_remote.name)
            _new_ref = self._remote_manager.get_recipe(conan_reference, the_remote)
            self._registry.refs.set(_new_ref, the_remote.name)
            recorder.recipe_downloaded(conan_reference, the_remote.url)
            return _new_ref

        if remote_name:
            output.info("Not found, retrieving from server '%s' " % remote_name)
            remote = self._registry.remotes.get(remote_name)
        else:
            remote = self._registry.refs.get(conan_reference)
            if remote:
                output.info("Retrieving from predefined remote '%s'" % remote.name)

        if remote:
            try:
                new_ref = _retrieve_from_remote(remote)
                return remote, new_ref
            except NotFoundException:
                msg = "%s was not found in remote '%s'" % (str(conan_reference), remote.name)
                recorder.recipe_install_error(conan_reference, INSTALL_ERROR_MISSING,
                                              msg, remote.url)
                raise NotFoundException(msg)
            except RequestException as exc:
                recorder.recipe_install_error(conan_reference, INSTALL_ERROR_NETWORK,
                                              str(exc), remote.url)
                raise exc

        output.info("Not found in local cache, looking in remotes...")
        remotes = self._registry.remotes.list
        if not remotes:
            raise ConanException("No remote defined")
        for remote in remotes:
            logger.debug("Trying with remote %s" % remote.name)
            try:
                new_ref = _retrieve_from_remote(remote)
                return remote, new_ref
            # If not found continue with the next, else raise
            except NotFoundException:
                pass
        else:
            msg = "Unable to find '%s' in remotes" % str(conan_reference)
            logger.debug("Not found in any remote")
            recorder.recipe_install_error(conan_reference, INSTALL_ERROR_MISSING,
                                          msg, None)
            raise NotFoundException(msg)

    def search_remotes(self, pattern, remote_name):
        if remote_name:
            remote = self._registry.remotes.get(remote_name)
            search_result = self._remote_manager.search_recipes(remote, pattern, ignorecase=False)
            return search_result

        for remote in self._registry.remotes.list:
            search_result = self._remote_manager.search_recipes(remote, pattern, ignorecase=False)
            if search_result:
                return search_result
